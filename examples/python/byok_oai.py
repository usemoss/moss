from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient, MutationOptions, QueryOptions
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

MOSS_PROJECT_ID = os.environ["MOSS_PROJECT_ID"]
MOSS_PROJECT_KEY = os.environ["MOSS_PROJECT_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
TOP_K = 5
INDEX_NAME = "locomo-byok"
DATA_FILE = Path(__file__).parent / "locomo_sample0.json"
EMBED_BATCH = 100
MIN_CONTENT_LEN = 3

SYSTEM_PROMPT = """You are a memory-augmented assistant answering questions about a long-running conversation between two people.

Each turn, you receive the top-{k} most semantically relevant past turns, retrieved by a vector search over the full conversation log. Each retrieved turn is tagged with the speaker's name, the session number, and the session date/time.

Use the retrieved turns as your primary source of grounded facts about what either speaker has said or done. If the retrieved context is clearly relevant, reference it concretely (paraphrase the turn and name the speaker). If the context is unrelated to the question, say so honestly rather than inventing details. Stay conversational and concise; do not list the retrieved turns back verbatim.
"""

HELP = """commands:
  > <text>          semantic search
  :add <text>       add a new doc to the index
  :list             show first 20 docs
  :count            show total docs
  :help             show this help
  :quit             exit (index is preserved)
"""


class InteractiveSession:
    def __init__(self) -> None:
        self.openai = OpenAI(api_key=OPENAI_API_KEY)
        self.moss = MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY)
        self.index_name = INDEX_NAME
        self.docs: dict[str, str] = {}

    def _embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.openai.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]

    def _embed_batched(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            chunk = texts[i : i + EMBED_BATCH]
            print(f"  embedding batch {i // EMBED_BATCH + 1} ({len(chunk)} docs)...")
            out.extend(self._embed(chunk))
        return out

    def _load_corpus(self) -> list[dict]:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        turns = data["turns"]
        kept = [
            t
            for t in turns
            if t.get("text") and len(t["text"].strip()) >= MIN_CONTENT_LEN
        ]
        skipped = len(turns) - len(kept)
        print(
            f"loaded {len(kept)} turns from {DATA_FILE.name} "
            f"(speakers: {data.get('speaker_a')} & {data.get('speaker_b')}, "
            f"sessions: {data.get('session_count')}, skipped {skipped} short/empty)"
        )
        return kept

    async def _index_exists(self) -> bool:
        try:
            indexes = await self.moss.list_indexes()
            return any(getattr(idx, "name", None) == self.index_name for idx in indexes)
        except Exception as exc:
            print(
                f"warning: list_indexes failed ({exc}); assuming index does not exist"
            )
            return False

    async def setup(self) -> None:
        if await self._index_exists():
            print(f"index '{self.index_name}' already exists — skipping ingest.")
            await self.moss.load_index(self.index_name)
            try:
                existing = await self.moss.get_docs(self.index_name)
                self.docs = {d.id: d.text for d in existing}
                print(f"  index loaded; hydrated {len(self.docs)} docs from Moss.\n")
            except Exception as exc:
                self.docs = {}
                print(f"  index loaded; warning: could not fetch docs back ({exc}).\n")
            return
        print(f"index '{self.index_name}' not found — running fresh ingest.")

        turns = self._load_corpus()
        texts = [t["text"] for t in turns]
        vectors = self._embed_batched(texts)
        docs = [
            DocumentInfo(
                id=t["dia_id"],
                text=t["text"],
                embedding=vec,
                metadata={
                    "speaker": t["speaker"],
                    "session": str(t["session"]),
                    "session_date_time": t["session_date_time"],
                },
            )
            for t, vec in zip(turns, vectors)
        ]

        print(f"creating Moss index '{self.index_name}' with {len(docs)} docs...")
        result = await self.moss.create_index(self.index_name, docs, model_id="custom")
        print(f"  ingested {result.doc_count} docs (vector dim = {len(vectors[0])})")

        self.docs = {d.id: d.text for d in docs}

        await self.moss.load_index(self.index_name)
        print("  index loaded.\n")

    async def query(self, text: str) -> None:
        vec = self._embed([text])[0]
        res = await self.moss.query(
            self.index_name, text, QueryOptions(embedding=vec, top_k=TOP_K)
        )

        if not res.docs:
            context = "(no relevant past turns found)"
        else:
            context_lines = []
            for doc in res.docs:
                meta = doc.metadata or {}
                speaker = meta.get("speaker", "?")
                session = meta.get("session", "?")
                ts = meta.get("session_date_time", "?")
                context_lines.append(
                    f"[{speaker} @ session {session}, {ts}] {doc.text}"
                )
            context = "\n".join(context_lines)

        answer = self._chat(text, context)
        print(f"\n  assistant: {answer}\n")

    def _chat(self, user_msg: str, context: str) -> str:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT.format(k=TOP_K)},
            {
                "role": "system",
                "content": f"Retrieved past messages:\n\n{context}",
            },
            {"role": "user", "content": user_msg},
        ]
        resp = self.openai.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.4,
        )
        return (resp.choices[0].message.content or "").strip()

    async def add(self, text: str) -> None:
        new_id = f"manual-{uuid.uuid4().hex[:8]}"
        vec = self._embed([text])[0]
        result = await self.moss.add_docs(
            self.index_name,
            [DocumentInfo(id=new_id, text=text, embedding=vec)],
            MutationOptions(upsert=True),
        )
        self.docs[new_id] = text
        print(
            f"  added [{new_id}] (job={result.job_id}, total docs={result.doc_count})"
        )

    def list_docs(self) -> None:
        if not self.docs:
            print("  (no in-memory doc cache — re-attached to existing index)")
            return
        for doc_id, text in list(self.docs.items())[:20]:
            snippet = text if len(text) <= 80 else text[:77] + "..."
            print(f"  [{doc_id}] {snippet}")
        if len(self.docs) > 20:
            print(f"  ... ({len(self.docs) - 20} more)")

    def count_docs(self) -> None:
        print(f"  in-memory docs: {len(self.docs)}")


async def repl(session: InteractiveSession) -> None:
    print(HELP)
    loop = asyncio.get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, input, "> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return

        line = line.strip()
        if not line:
            continue

        if line in (":quit", ":q", ":exit"):
            return
        if line in (":help", ":h", "?"):
            print(HELP)
            continue
        if line == ":list":
            session.list_docs()
            continue
        if line == ":count":
            session.count_docs()
            continue
        if line.startswith(":add "):
            text = line[5:].strip()
            if not text:
                print("  usage: :add <text>")
                continue
            await session.add(text)
            continue
        if line.startswith(":"):
            print(f"  unknown command: {line}. try :help")
            continue

        await session.query(line)


async def main() -> None:
    session = InteractiveSession()
    await session.setup()
    await repl(session)
    print(f"\nindex '{INDEX_NAME}' preserved. bye.")


if __name__ == "__main__":
    asyncio.run(main())
