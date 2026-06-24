"""Crawl public insurance sources and emit chunked MOSS DocumentInfo objects.

Sources:
  - iii.org        — Insurance Information Institute: homeowners coverage guides
  - fema.gov       — NFIP flood policy summaries and coverage explanations
  - naic.org       — Consumer guides to homeowners insurance
  - tdi.texas.gov  — Texas DOI consumer bulletins
  - insurance.ca.gov — California DOI consumer guides

Run:

    uv run python -m ingest.crawl --out data/crawled_kb.json

The output is a JSON array of {id, text, metadata} objects ready to pass
directly to MossClient.create_index(). Combine it with data/claims_kb.json
(hand-authored HO-3 policy language) to build the full shared claims-kb index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("ingest.crawl")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Crawl targets
# Each entry: (url, source_tag, topic_tag)
# ---------------------------------------------------------------------------

CRAWL_TARGETS: list[tuple[str, str, str]] = [
    # Insurance Information Institute — homeowners insurance overviews
    (
        "https://www.iii.org/article/what-is-homeowners-insurance",
        "iii.org",
        "homeowners_overview",
    ),
    (
        "https://www.iii.org/article/what-does-homeowners-insurance-cover",
        "iii.org",
        "coverage_guide",
    ),
    (
        "https://www.iii.org/article/how-much-homeowners-insurance-do-you-need",
        "iii.org",
        "coverage_limits",
    ),
    (
        "https://www.iii.org/article/homeowners-insurance-common-exclusions",
        "iii.org",
        "exclusions_guide",
    ),
    (
        "https://www.iii.org/article/what-is-a-homeowners-insurance-deductible",
        "iii.org",
        "deductibles_guide",
    ),
    (
        "https://www.iii.org/article/if-my-home-is-damaged-by-a-flood-am-i-covered",
        "iii.org",
        "flood_coverage",
    ),
    (
        "https://www.iii.org/article/water-damage-what-does-homeowners-insurance-cover",
        "iii.org",
        "water_damage",
    ),
    (
        "https://www.iii.org/article/what-if-there-is-a-dispute-with-my-insurance-company",
        "iii.org",
        "dispute_resolution",
    ),
    # FEMA — NFIP flood insurance consumer pages
    (
        "https://www.fema.gov/flood-insurance/nfip",
        "fema.gov",
        "nfip_overview",
    ),
    (
        "https://www.fema.gov/flood-insurance/understand-your-policy",
        "fema.gov",
        "nfip_policy",
    ),
    # Texas DOI
    (
        "https://www.tdi.texas.gov/pubs/consumer/cb020.html",
        "tdi.texas.gov",
        "texas_homeowners_guide",
    ),
    (
        "https://www.tdi.texas.gov/pubs/consumer/cb022.html",
        "tdi.texas.gov",
        "texas_water_damage",
    ),
    # California DOI
    (
        "https://www.insurance.ca.gov/01-consumers/105-type/95-guides/03-res/homeown-ins-guide.cfm",
        "insurance.ca.gov",
        "california_homeowners_guide",
    ),
    # NAIC consumer guides
    (
        "https://content.naic.org/consumer/homeowners-insurance",
        "naic.org",
        "naic_homeowners_guide",
    ),
]

# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; InsuranceAdjusterDemo/1.0; "
        "educational research; +https://moss.dev)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 20.0
INTER_REQUEST_DELAY = 1.5  # seconds — polite crawling


def fetch_html(url: str, client: httpx.Client) -> str | None:
    """Fetch a page and return the HTML string, or None on error."""
    try:
        resp = client.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} for {url}")
    except httpx.RequestError as e:
        logger.warning(f"Request error for {url}: {e}")
    return None


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

# Tags whose text we want; these typically contain the article body
CONTENT_TAGS = ("article", "main", "section", "[role=main]", "div.content", "div.article-body")

# Tags to strip (navigation, ads, footers)
STRIP_TAGS = ("nav", "header", "footer", "aside", "script", "style", "noscript", "form")


def extract_text(html: str, url: str) -> str:
    """Extract clean article text from an HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove boilerplate tags
    for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style", "noscript", "form"]):
        tag.decompose()

    # Try to find the main content area
    body = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("div", class_=re.compile(r"content|article|body|post", re.I))
        or soup.body
    )
    if body is None:
        return ""

    # Extract text with whitespace normalization
    raw = body.get_text(separator="\n", strip=True)
    # Collapse excessive blank lines
    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

@dataclass
class RawChunk:
    text: str
    source_url: str
    source: str
    topic: str


def _split_into_paragraphs(text: str, min_len: int = 80) -> list[str]:
    """Split on double-newlines; discard tiny fragments."""
    paras = re.split(r"\n{2,}", text)
    out: list[str] = []
    pending = ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(p) < min_len:
            # Accumulate short paragraphs into the previous chunk
            pending = (pending + " " + p).strip() if pending else p
        else:
            if pending:
                out.append(pending)
                pending = ""
            out.append(p)
    if pending:
        out.append(pending)
    return out


def _window_chunks(paragraphs: list[str], max_chars: int = 800, overlap: int = 1) -> Generator[str, None, None]:
    """Sliding-window over paragraphs to produce ~max_chars chunks with 1-para overlap."""
    i = 0
    while i < len(paragraphs):
        chunk_parts: list[str] = []
        total = 0
        j = i
        while j < len(paragraphs) and total + len(paragraphs[j]) < max_chars:
            chunk_parts.append(paragraphs[j])
            total += len(paragraphs[j])
            j += 1
        if not chunk_parts:
            # Single paragraph exceeds max_chars — emit it as-is
            chunk_parts = [paragraphs[i]]
            j = i + 1
        yield "\n\n".join(chunk_parts)
        i = max(i + 1, j - overlap)


def chunk_text(text: str, source_url: str, source: str, topic: str, max_chars: int = 800) -> list[RawChunk]:
    """Chunk extracted page text into retrieval-sized pieces."""
    if len(text) < 100:
        return []
    paras = _split_into_paragraphs(text)
    chunks: list[RawChunk] = []
    for chunk_text in _window_chunks(paras, max_chars=max_chars):
        if len(chunk_text.strip()) < 60:
            continue
        chunks.append(RawChunk(
            text=chunk_text.strip(),
            source_url=source_url,
            source=source,
            topic=topic,
        ))
    return chunks


# ---------------------------------------------------------------------------
# Document ID generation
# ---------------------------------------------------------------------------

def _chunk_id(source: str, topic: str, index: int) -> str:
    base = f"{source}::{topic}::{index}"
    h = hashlib.sha1(base.encode()).hexdigest()[:8]
    return f"crawled-{source.replace('.', '-')}-{topic}-{h}"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def crawl_all(targets: list[tuple[str, str, str]], delay: float = INTER_REQUEST_DELAY) -> list[dict]:
    """Crawl all targets and return a list of MOSS document dicts."""
    docs: list[dict] = []

    with httpx.Client() as client:
        for i, (url, source, topic) in enumerate(targets):
            logger.info(f"[{i + 1}/{len(targets)}] Fetching {url}")
            html = fetch_html(url, client)
            if html is None:
                logger.warning(f"  Skipped (fetch failed)")
                if i < len(targets) - 1:
                    time.sleep(delay)
                continue

            text = extract_text(html, url)
            if len(text) < 200:
                logger.warning(f"  Skipped (too little text extracted: {len(text)} chars)")
                if i < len(targets) - 1:
                    time.sleep(delay)
                continue

            chunks = chunk_text(text, source_url=url, source=source, topic=topic)
            logger.info(f"  {len(chunks)} chunks from {len(text)} chars")

            for idx, chunk in enumerate(chunks):
                docs.append({
                    "id": _chunk_id(source, topic, idx),
                    "text": chunk.text,
                    "metadata": {
                        "source": chunk.source,
                        "source_url": chunk.source_url,
                        "topic": chunk.topic,
                        "chunk_index": str(idx),
                    },
                })

            if i < len(targets) - 1:
                time.sleep(delay)

    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl public insurance sources for the claims-kb index.")
    parser.add_argument(
        "--out",
        default="data/crawled_kb.json",
        help="Output JSON path (default: data/crawled_kb.json)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=INTER_REQUEST_DELAY,
        help=f"Seconds between requests (default: {INTER_REQUEST_DELAY})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print targets without fetching",
    )
    args = parser.parse_args()

    if args.dry_run:
        print(f"Would crawl {len(CRAWL_TARGETS)} URLs:")
        for url, source, topic in CRAWL_TARGETS:
            print(f"  [{source}] {url}")
        return

    docs = crawl_all(CRAWL_TARGETS, delay=args.delay)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(docs, indent=2))
    logger.info(f"Wrote {len(docs)} documents to {out_path}")


if __name__ == "__main__":
    main()
