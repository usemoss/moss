"""Text chunking utilities for insurance policy PDFs and HTML pages.

Use this when ingesting longer documents (PDFs, policy forms) rather than
short article pages. The crawl.py module handles HTML; this module handles
structured long-form text (e.g., a 40-page HO-3 policy PDF).

Usage:

    from ingest.chunk import chunk_policy_pdf, chunk_policy_text

    # From a PDF file
    docs = chunk_policy_pdf("path/to/policy.pdf", policy_number="FL-HO3-001", state="FL")

    # From pre-extracted text
    docs = chunk_policy_text(text, doc_id_prefix="ca-doi-guide", source="insurance.ca.gov")
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

try:
    import pdfplumber

    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class PolicyChunk:
    id: str
    text: str
    metadata: dict[str, str]


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

# Pattern: lines that look like section/article headers
_SECTION_HEADER_RE = re.compile(
    r"^(SECTION\s+[IVX]+|ARTICLE\s+\d+|COVERAGE\s+[A-F]|"
    r"DEFINITIONS|CONDITIONS|EXCLUSIONS?|ENDORSEMENT|"
    r"[A-Z][A-Z\s\-]{4,}:?)\s*$",
    re.MULTILINE,
)


def _detect_section(text: str) -> str:
    """Return the most likely section label from a chunk's first few lines."""
    first_lines = "\n".join(text.splitlines()[:3]).upper()
    if "EXCLUSION" in first_lines:
        return "exclusions"
    if "COVERAGE A" in first_lines:
        return "coverage_a"
    if "COVERAGE B" in first_lines:
        return "coverage_b"
    if "COVERAGE C" in first_lines:
        return "coverage_c"
    if "COVERAGE D" in first_lines:
        return "coverage_d"
    if "COVERAGE E" in first_lines or "LIABILITY" in first_lines:
        return "liability"
    if "DEDUCTIBLE" in first_lines:
        return "deductibles"
    if "DEFINITION" in first_lines:
        return "definitions"
    if "CONDITION" in first_lines:
        return "conditions"
    if "ENDORSEMENT" in first_lines:
        return "endorsement"
    if "FLOOD" in first_lines:
        return "flood"
    if "EARTHQUAKE" in first_lines:
        return "earthquake"
    return "general"


# ---------------------------------------------------------------------------
# PDF ingestion
# ---------------------------------------------------------------------------


def chunk_policy_pdf(
    pdf_path: str | Path,
    *,
    policy_number: str = "unknown",
    state: str = "",
    source: str = "policy_pdf",
    max_chars: int = 900,
) -> list[PolicyChunk]:
    """Extract text from a policy PDF and chunk it for MOSS indexing.

    Requires pdfplumber (`pip install pdfplumber`).
    """
    if not _PDFPLUMBER_AVAILABLE:
        raise ImportError(
            "pdfplumber is required for PDF ingestion: pip install pdfplumber"
        )

    path = Path(pdf_path)
    with pdfplumber.open(path) as pdf:
        pages_text = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)

    full_text = "\n".join(pages_text)
    return chunk_policy_text(
        full_text,
        doc_id_prefix=f"pdf-{policy_number.lower().replace(' ', '-')}",
        source=source,
        extra_metadata={"policy_number": policy_number, "state": state},
        max_chars=max_chars,
    )


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


def _split_on_sections(text: str) -> list[tuple[str, str]]:
    """Split text on detected section headers, returning (section_label, content) pairs."""
    segments: list[tuple[str, str]] = []
    current_label = "preamble"
    current_parts: list[str] = []

    for line in text.splitlines():
        is_header = bool(_SECTION_HEADER_RE.match(line.strip()))
        if is_header and current_parts:
            segments.append((current_label, "\n".join(current_parts).strip()))
            current_parts = []
            current_label = line.strip().lower().replace(" ", "_")[:40]
        else:
            current_parts.append(line)

    if current_parts:
        segments.append((current_label, "\n".join(current_parts).strip()))

    return [(lbl, text) for lbl, text in segments if text.strip()]


def _paragraph_chunks(text: str, max_chars: int) -> list[str]:
    """Break a section into paragraph-aligned chunks of at most max_chars."""
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paras:
        if current_len + len(para) > max_chars and current:
            chunks.append("\n\n".join(current))
            # Overlap: keep the last paragraph for context
            current = [current[-1], para]
            current_len = len(current[-2]) + len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _chunk_id(prefix: str, section: str, index: int) -> str:
    base = f"{prefix}::{section}::{index}"
    h = hashlib.sha1(base.encode()).hexdigest()[:8]
    return f"{prefix}-{section[:20]}-{h}"


def chunk_policy_text(
    text: str,
    *,
    doc_id_prefix: str,
    source: str,
    extra_metadata: dict[str, str] | None = None,
    max_chars: int = 900,
) -> list[PolicyChunk]:
    """Chunk a long policy text into MOSS-ready PolicyChunk objects.

    Strategy:
      1. Split on section headers (COVERAGE A, EXCLUSIONS, etc.)
      2. Within each section, apply paragraph-aware chunking at max_chars
      3. Attach section label and source metadata to each chunk
    """
    base_meta: dict[str, str] = {"source": source}
    if extra_metadata:
        base_meta.update(extra_metadata)

    sections = _split_on_sections(text)
    chunks: list[PolicyChunk] = []

    for section_label, section_text in sections:
        if len(section_text) < 50:
            continue
        sub_chunks = _paragraph_chunks(section_text, max_chars=max_chars)
        for idx, sub in enumerate(sub_chunks):
            if len(sub.strip()) < 40:
                continue
            chunk_section = (
                _detect_section(sub) if section_label == "preamble" else section_label
            )
            meta = {**base_meta, "section": chunk_section, "chunk_index": str(idx)}
            chunks.append(
                PolicyChunk(
                    id=_chunk_id(doc_id_prefix, chunk_section, len(chunks)),
                    text=sub.strip(),
                    metadata=meta,
                )
            )

    return chunks


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------


def merge_doc_lists(*lists: Sequence[dict]) -> list[dict]:
    """Deduplicate and merge multiple lists of MOSS document dicts by ID."""
    seen: set[str] = set()
    merged: list[dict] = []
    for lst in lists:
        for doc in lst:
            if doc["id"] not in seen:
                seen.add(doc["id"])
                merged.append(doc)
    return merged
