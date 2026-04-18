from __future__ import annotations

import asyncio
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from inferedge_moss import MossClient
from moss_core import QueryOptions

load_dotenv(Path(__file__).parent.parent / ".env")

PROJECT_ID = os.getenv("MOSS_IMAGE_SEARCH_DEMO_PROJECT_ID", "")
PROJECT_KEY = os.getenv("MOSS_IMAGE_SEARCH_DEMO_PROJECT_KEY", "")
BASE_INDEX_NAME = os.getenv("MOSS_INDEX_NAME", "coco-data")
S3_BUCKET = os.getenv("S3_BUCKET", "")

TOP_K_DEFAULT = 5

client = MossClient(PROJECT_ID, PROJECT_KEY)

_loaded_indexes: set[str] = set()
_index_locks: dict[str, asyncio.Lock] = {}

_s3_loader = None
_PHOTO_ID_RE = re.compile(r"^\d+$")


def _get_index_name(tier: str) -> str:
    return f"{BASE_INDEX_NAME}-{tier}"


async def _ensure_index_loaded(index_name: str) -> None:
    if index_name in _loaded_indexes:
        return
    lock = _index_locks.setdefault(index_name, asyncio.Lock())
    async with lock:
        if index_name not in _loaded_indexes:
            await client.load_index(index_name)
            _loaded_indexes.add(index_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _s3_loader
    if S3_BUCKET:
        from s3_loader import S3DataLoader

        aws_region = os.getenv("AWS_REGION", "us-east-1")
        _s3_loader = S3DataLoader(S3_BUCKET, aws_region)
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def add_hsts_header(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=30"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/demo/image-search")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/search")
async def search(
    query: str = Query(..., min_length=1),
    tier: str = Query("1k"),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=50),
) -> dict[str, Any]:
    index_name = _get_index_name(tier)

    try:
        await _ensure_index_loaded(index_name)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to load index: {exc}") from exc

    try:
        result = await client.query(index_name, query.lower(), QueryOptions(top_k=top_k))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc

    docs = [
        {
            "id": doc.id,
            "text": doc.text,
            "score": doc.score,
            "metadata": doc.metadata if doc.metadata is not None else {},
        }
        for doc in (result.docs or [])
    ]

    return {
        "docs": docs,
        "timeTakenInMs": result.time_taken_ms,
    }


@router.get("/photos/{photo_id}")
async def get_photo(photo_id: str) -> Response:
    """Serve a COCO photo by ID, streamed from S3."""
    if not _PHOTO_ID_RE.match(photo_id):
        raise HTTPException(status_code=400, detail="Invalid photo ID format.")

    if _s3_loader is None:
        raise HTTPException(status_code=503, detail="Photo serving not configured (S3_BUCKET not set).")

    photo_bytes = await asyncio.to_thread(_s3_loader.get_photo_bytes, photo_id)
    if photo_bytes is None:
        raise HTTPException(status_code=404, detail="Photo not found.")

    return Response(
        content=photo_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
