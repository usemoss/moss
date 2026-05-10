"""Build one Moss index per PNR fixture for the airline customer voice agent.

Each booking gets its own index named ``booking-<pnr_lowercased>``. The
agent loads the right index when the caller provides their PNR; switching
to a companion booking is just another ``load_index`` call against the
same warm in-process runtime.

Run before starting the agent:

    uv run python create_indexes.py             # build all PNR fixtures
    uv run python create_indexes.py --pnr WJ7BNH  # build just one
    uv run python create_indexes.py --list        # list available fixtures
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"See .env.example for the full list of keys this example needs."
        )
    return value


def _discover_fixtures() -> dict[str, Path]:
    """Map PNR (uppercase) to its fixture file path."""
    out: dict[str, Path] = {}
    for path in sorted(DATA_DIR.glob("pnr_*.json")):
        # filename pattern: pnr_<lowercase pnr>.json
        pnr = path.stem.removeprefix("pnr_").upper()
        out[pnr] = path
    return out


def _index_name_for(pnr: str) -> str:
    return f"booking-{pnr.lower()}"


def _load_documents(path: Path) -> list[DocumentInfo]:
    raw = json.loads(path.read_text())
    docs: list[DocumentInfo] = []
    for doc in raw:
        # Moss requires string-valued metadata. Coerce so the JSON can
        # still write ints/bools naturally (e.g., "segment": 1).
        metadata = {k: str(v) for k, v in doc.get("metadata", {}).items()}
        docs.append(DocumentInfo(id=doc["id"], text=doc["text"], metadata=metadata))
    return docs


async def build_one(client: MossClient, pnr: str, path: Path) -> str:
    index = _index_name_for(pnr)
    docs = _load_documents(path)
    print(f"  building {index} ({len(docs)} docs from {path.name})...")
    await client.create_index(index, docs)
    return index


async def build_all(only_pnr: str | None = None) -> None:
    project_id = _require_env("MOSS_PROJECT_ID")
    project_key = _require_env("MOSS_PROJECT_KEY")
    client = MossClient(project_id, project_key)

    fixtures = _discover_fixtures()
    if only_pnr:
        only_pnr = only_pnr.upper()
        if only_pnr not in fixtures:
            raise SystemExit(
                f"PNR {only_pnr} has no fixture. Available: {', '.join(sorted(fixtures))}"
            )
        fixtures = {only_pnr: fixtures[only_pnr]}

    print(f"Creating {len(fixtures)} Moss index(es)...")
    for pnr, path in fixtures.items():
        await build_one(client, pnr, path)
    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build per-PNR Moss indexes for the airline customer voice agent example."
    )
    parser.add_argument("--pnr", help="Build a single PNR (e.g. WJ7BNH).")
    parser.add_argument("--list", action="store_true", help="List available fixtures and exit.")
    args = parser.parse_args()

    fixtures = _discover_fixtures()
    if args.list:
        print("Available PNR fixtures:")
        for pnr, path in fixtures.items():
            print(f"  {pnr:8} -> {path.name}  (index: {_index_name_for(pnr)})")
        return

    asyncio.run(build_all(args.pnr))


if __name__ == "__main__":
    main()
