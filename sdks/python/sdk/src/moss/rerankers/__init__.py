from __future__ import annotations

from typing import Any, Dict, Type

from .base import Reranker

_REGISTRY: Dict[str, Type[Reranker]] = {}

_MISSING_PROVIDERS: Dict[str, str] = {}


def register_reranker(name: str, cls: Type[Reranker]) -> None:
    """Register a reranker class under a provider name.

    Example:
        class MyReranker:
            async def rerank(self, query, documents, top_k=None, **kwargs):
                ...

        register_reranker("my-reranker", MyReranker)
    """
    _REGISTRY[name] = cls


def get_reranker(name: str, **kwargs: Any) -> Reranker:
    """Instantiate a reranker by provider name.

    Raises:
        ImportError: If the provider is built-in but its optional dependency
            isn't installed (e.g. "cohere" without `pip install cohere`).
        ValueError: If the provider name is not registered and not a known
            built-in.
    """
    if name in _MISSING_PROVIDERS:
        package = _MISSING_PROVIDERS[name]
        raise ImportError(
            f"The '{name}' reranker requires the '{package}' package. "
            f"Install it with: pip install {package}"
        )
    if name not in _REGISTRY:
        available = list(_REGISTRY) or ["(none registered)"]
        raise ValueError(
            f"Unknown reranker provider: '{name}'. "
            f"Available: {available}. "
            f"Register custom rerankers with register_reranker(name, cls)."
        )
    return _REGISTRY[name](**kwargs)


__all__ = ["Reranker", "register_reranker", "get_reranker"]

try:
    from .cohere import CohereReranker

    register_reranker("cohere", CohereReranker)
except ImportError:
    # `pip install cohere` to enable the Cohere reranker.
    _MISSING_PROVIDERS["cohere"] = "cohere"
