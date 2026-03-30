from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(init=False)
class RerankOptions:
    """Configuration for reranking passed to query().

    Example:
        rerank=RerankOptions(provider="cohere", api_key="...", top_n=5)

    The provider name maps to a reranker class via the registry in
    moss.rerankers. Any additional kwargs are passed to the reranker
    constructor (e.g. api_key, model).
    """

    provider: str
    top_n: Optional[int]
    init_kwargs: Dict[str, Any]

    def __init__(
        self,
        provider: str,
        top_n: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        self.provider = provider
        self.top_n = top_n
        self.init_kwargs = kwargs
        self._instance: Optional[Any] = None
