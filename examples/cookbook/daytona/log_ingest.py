import asyncio
import hashlib
import logging
import re
from typing import List, Optional

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



async def get_log_search_tool(
    project_id: str,
    project_key: str,
    index_name: str,
    top_k: int = 10,
    alpha: float = 0.7,
) -> Tool:
    """Load the MOSS index then return a LangChain Tool ready for querying."""
    client = MossClient(project_id, project_key)
    await client.load_index(index_name)

    async def asearch(query: str) -> str:
        results = await client.query(index_name, query, QueryOptions(top_k=top_k, alpha=alpha))
        if not results.docs:
            return "No relevant log entries found."
        lines = []
        for i, doc in enumerate(results.docs, 1):
            level = doc.metadata.get("level", "?")
            source = doc.metadata.get("source", "?")
            lines.append(f"Log {i} [{level}] [{source}] (score={doc.score:.2f}):\n{doc.text}")
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
