#
# Copyright (c) 2025, InferEdge Inc.
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Context formatting helpers for Moss search results."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

__all__ = ["DefaultContextFormatter"]


class DefaultContextFormatter:
    r"""Format Moss search results into a context string for LLM consumption.

    Usage::

        formatter = DefaultContextFormatter(prefix="Context:\n\n")
        text = formatter(documents)  # str | None
    """

    def __init__(
        self,
        *,
        prefix: str = "Relevant context from knowledge base:\n\n",
    ) -> None:
        """Initialize with a prefix for the formatted output.

        Args:
            prefix: Text prepended to the formatted document list.
        """
        self._prefix = prefix

    def __call__(self, documents: Sequence[Any]) -> str | None:
        """Format documents into a numbered context string.

        Args:
            documents: Sequence of Moss document objects with `text`, `metadata`,
                and optionally `score` attributes.

        Returns:
            Formatted string, or None if the document list is empty.
        """
        if not documents:
            return None

        lines = [self._prefix.rstrip(), ""]
        for idx, doc in enumerate(documents, start=1):
            text = getattr(doc, "text", "") or ""
            meta = getattr(doc, "metadata", None) or {}
            extras = []

            if source := meta.get("source"):
                extras.append(f"source={source}")
            if (score := getattr(doc, "score", None)) is not None:
                extras.append(f"score={score}")

            suffix = f" ({', '.join(extras)})" if extras else ""
            lines.append(f"{idx}. {text}{suffix}")

        return "\n".join(lines)
