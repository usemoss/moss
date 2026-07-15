"""Configuration model for the Moss session manager in TEN extensions."""

from __future__ import annotations

from pydantic import BaseModel


class MossSessionConfig(BaseModel):
    """Standardized `moss_*` properties consumed from a TEN `property.json`.

    A TEN extension's own config model can inherit these fields so property
    names stay consistent across integrations.
    """

    moss_project_id: str = ""
    moss_project_key: str = ""
    moss_index_name: str = ""
    moss_model_id: str = "moss-minilm"
    moss_top_k: int = 5
    moss_alpha: float = 0.8
    moss_context_header: str = "Relevant knowledge from Moss:"
    enable_moss: bool = True
