"""Build the Moss indexes for the candidate screening voice agent.

Two indexes power the screening:
  - one for the job description       (default name: ``job-senior-backend-payments``)
  - one for the candidate's resume    (default name: ``candidate-strong-match``)

Both fixtures live in ``data/`` as flat JSON arrays of ``{id, text, metadata}``
documents - the native Moss shape. Index names are derived from the
fixture filename, with the leading ``job_`` / ``candidate_`` and the
``.json`` suffix stripped, then underscores swapped for dashes.

Run before starting the agent:

    uv run python create_indexes.py                       # default JD + strong-match candidate
    uv run python create_indexes.py --candidate partial   # use a different candidate fixture

Use ``--list`` to see the available fixtures.
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

JOB_FIXTURE = "job_senior_backend_payments.json"
CANDIDATE_FIXTURES = {
    "strong":  "candidate_strong_match.json",
    "partial": "candidate_partial_match.json",
    "junior":  "candidate_junior_reach.json",
}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"See .env.example for the full list of keys this example needs."
        )
    return value


def _index_name_from_filename(filename: str) -> str:
    """``candidate_strong_match.json`` -> ``candidate-strong-match``."""
    stem = Path(filename).stem
    return stem.replace("_", "-")


def _load_documents(filename: str) -> list[DocumentInfo]:
    with (DATA_DIR / filename).open() as f:
        raw = json.load(f)
    return [
        DocumentInfo(
            id=doc["id"],
            text=doc["text"],
            metadata=doc.get("metadata", {}),
        )
        for doc in raw
    ]


async def build_indexes(candidate_key: str) -> tuple[str, str]:
    """Create both indexes and return (job_index_name, candidate_index_name)."""
    project_id = _require_env("MOSS_PROJECT_ID")
    project_key = _require_env("MOSS_PROJECT_KEY")
    client = MossClient(project_id, project_key)

    candidate_filename = CANDIDATE_FIXTURES[candidate_key]
    job_index = os.getenv("MOSS_JOB_INDEX_NAME", _index_name_from_filename(JOB_FIXTURE))
    candidate_index = os.getenv(
        "MOSS_CANDIDATE_INDEX_NAME",
        _index_name_from_filename(candidate_filename),
    )

    job_docs = _load_documents(JOB_FIXTURE)
    candidate_docs = _load_documents(candidate_filename)

    print(f"Creating job index '{job_index}' with {len(job_docs)} documents...")
    await client.create_index(job_index, job_docs)

    print(f"Creating candidate index '{candidate_index}' with {len(candidate_docs)} documents...")
    await client.create_index(candidate_index, candidate_docs)

    print("Both indexes ready.")
    print(f"  MOSS_JOB_INDEX_NAME={job_index}")
    print(f"  MOSS_CANDIDATE_INDEX_NAME={candidate_index}")
    return job_index, candidate_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Moss indexes for the candidate screening demo.")
    parser.add_argument(
        "--candidate",
        choices=list(CANDIDATE_FIXTURES),
        default="strong",
        help="Which candidate fixture to index (default: strong).",
    )
    parser.add_argument("--list", action="store_true", help="List available fixtures and exit.")
    args = parser.parse_args()

    if args.list:
        print("Available candidate fixtures:")
        for key, filename in CANDIDATE_FIXTURES.items():
            print(f"  {key:8} -> {filename:40} -> index '{_index_name_from_filename(filename)}'")
        return

    asyncio.run(build_indexes(args.candidate))


if __name__ == "__main__":
    main()
