import asyncio
import hashlib
import logging
import re
from typing import Any, List, Optional

from pydantic import Field, PrivateAttr
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.tools import Tool

from moss import MossClient, QueryOptions, DocumentInfo

logger = logging.getLogger(__name__)

# Single cheap scan to tag severity — everything else is left to MOSS semantics
_LEVEL_RE = re.compile(
    r"\b(CRITICAL|FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE|NOTICE)\b",
    re.IGNORECASE,
)
_LEVEL_NORM = {"WARNING": "WARN", "FATAL": "ERROR", "NOTICE": "INFO", "TRACE": "DEBUG"}


def parse_log_line(line: str, source: str = "unknown") -> Optional[DocumentInfo]:
    """
    Store a raw log line as a :class:`~moss.DocumentInfo`.

    The full line is kept as ``text`` so MOSS can semantically search it.
    Only ``source`` and ``level`` are extracted as metadata — everything else
    (timestamp, service, message) is understood by the LLM at query time.
    Returns ``None`` for blank / comment lines.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    lm = _LEVEL_RE.search(line)
    level = lm.group(1).upper() if lm else "INFO"
    level = _LEVEL_NORM.get(level, level)

    doc_id = f"{source}::{hashlib.md5(f'{line}:{id(line)}:{hash((line, source))}'.encode()).hexdigest()[:12]}"
    return DocumentInfo(id=doc_id, text=line, metadata={"source": source, "level": level})


def parse_log_lines(lines: List[str], source: str) -> List[DocumentInfo]:
    """Parse a list of raw log lines, skipping blanks."""
    docs = []
    for line in lines:
        doc = parse_log_line(line, source=source)
        if doc:
            docs.append(doc)
    return docs


#: Default shell commands to harvest logs from a sandbox.
#: Each tuple is ``(source_name, shell_command)``.
DEFAULT_LOG_COMMANDS: List[tuple] = [
    ("app", "cat /tmp/app.log 2>/dev/null || true"),
    ("syslog", "tail -n 500 /var/log/syslog 2>/dev/null || true"),
    ("dmesg", "dmesg 2>/dev/null | tail -n 200 || true"),
    ("auth", "tail -n 200 /var/log/auth.log 2>/dev/null || true"),
]


def collect_logs_from_sandbox(
    sandbox,
    commands: Optional[List[tuple]] = None,
) -> List[DocumentInfo]:
    """
    Run log-collection commands inside a Daytona sandbox and parse the output.

    Each shell command is executed via ``sandbox.process.code_run`` using Python's
    ``subprocess`` module so we stay within the ``code_run`` API.

    Args:
        sandbox:  A Daytona sandbox object (must support ``sandbox.process.code_run``).
        commands: List of ``(source_name, shell_command)`` pairs.
                  Defaults to :data:`DEFAULT_LOG_COMMANDS`.

    Returns:
        Flat list of :class:`~moss.DocumentInfo` for every parsed log line.
    """
    if commands is None:
        commands = DEFAULT_LOG_COMMANDS

    all_docs: List[DocumentInfo] = []
    for source_name, cmd in commands:
        # Wrap the shell command in Python subprocess so we only use code_run
        python_code = (
            "import subprocess\n"
            f"r = subprocess.run({cmd!r}, shell=True, capture_output=True, text=True)\n"
            "print(r.stdout)\n"
        )
        try:
            response = sandbox.process.code_run(python_code)
            if response.exit_code != 0:
                logger.warning("Command '%s' exited %d", source_name, response.exit_code)
                continue
            output: str = response.result or ""
            lines = [ln for ln in output.splitlines() if ln.strip()]
            if lines:
                docs = parse_log_lines(lines, source=source_name)
                all_docs.extend(docs)
                logger.info("Collected %d entries from '%s'", len(docs), source_name)
        except Exception as exc:
            logger.warning("Failed to collect logs from '%s': %s", source_name, exc)

    logger.info("Total log entries collected: %d", len(all_docs))
    return all_docs



class LogSearchRetriever(BaseRetriever):
    """Semantic / hybrid search retriever over indexed log entries."""

    project_id: str = Field(description="Moss project ID")
    project_key: str = Field(description="Moss project key")
    index_name: str = Field(description="Name of the Moss log index")
    top_k: int = Field(default=10, description="Number of results to return")
    alpha: float = Field(default=0.7, description="Search blend (0=keyword, 1=semantic)")

    _client: Any = PrivateAttr()
    _index_loaded: bool = PrivateAttr(default=False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = MossClient(self.project_id, self.project_key)

    async def _ensure_loaded(self) -> None:
        if not self._index_loaded:
            await self._client.load_index(self.index_name)
            self._index_loaded = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        try:
            return asyncio.run(self._aget_relevant_documents(query))
        except RuntimeError as exc:
            if "asyncio.run() cannot be called from a running event loop" in str(exc):
                raise RuntimeError(
                    "LogSearchRetriever cannot be called from a running event loop. "
                    "Use 'await retriever.ainvoke()' instead."
                ) from exc
            raise

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[AsyncCallbackManagerForRetrieverRun] = None,
    ) -> List[Document]:
        await self._ensure_loaded()
        results = await self._client.query(
            self.index_name,
            query,
            QueryOptions(top_k=self.top_k, alpha=self.alpha),
        )
        docs = []
        for doc in results.docs:
            docs.append(
                Document(
                    page_content=doc.text,
                    metadata={
                        "score": doc.score,
                        "id": doc.id,
                        "source": doc.metadata.get("source", ""),
                        "level": doc.metadata.get("level", ""),
                    },
                )
            )
        return docs


def get_log_search_tool(
    project_id: str,
    project_key: str,
    index_name: str,
    top_k: int = 10,
    alpha: float = 0.7,
) -> Tool:
    """
    Create a LangChain :class:`~langchain_core.tools.Tool` for querying logs.

    The returned tool can be handed directly to any LangChain agent.

    Args:
        project_id:  Moss project ID.
        project_key: Moss project key.
        index_name:  Name of the pre-created log index.
        top_k:       How many log entries to retrieve per query.
        alpha:       Hybrid-search blend — 0 = pure keyword, 1 = pure semantic.
    """
    retriever = LogSearchRetriever(
        project_id=project_id,
        project_key=project_key,
        index_name=index_name,
        top_k=top_k,
        alpha=alpha,
    )

    async def asearch(query: str) -> str:
        docs = await retriever._aget_relevant_documents(query)
        if not docs:
            return "No relevant log entries found."
        lines = []
        for i, doc in enumerate(docs, 1):
            m = doc.metadata
            level = m.get("level", "?")
            source = m.get("source", "?")
            score = m.get("score", 0)
            lines.append(
                f"Log {i} [{level}] [{source}] (score={score:.2f}):\n"
                f"{doc.page_content}"
            )
        return "\n\n".join(lines)

    def search(query: str) -> str:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            raise RuntimeError("Cannot use sync log_search inside an event loop.")
        return asyncio.run(asearch(query))

    return Tool(
        name="log_search",
        description=(
            "Search indexed system logs for relevant entries. "
            "Use to investigate errors, warnings, authentication failures, "
            "service events, performance issues, or any system activity. "
            "Input: natural language description of what you want to find."
        ),
        func=search,
        coroutine=asearch,
    )
