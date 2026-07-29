"""Configuration model for the Moss session manager in TEN extensions."""

from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr


class MossSessionConfig(BaseModel):
    """Standardized `moss_*` properties consumed from a TEN `property.json`.

    A TEN extension's own config model can inherit these fields so property
    names stay consistent across integrations.
    """

    moss_project_id: str = ""
    # SecretStr so the key stays masked in reprs / logs / model dumps;
    # MossSessionManager.from_config unwraps it via get_secret_value().
    moss_project_key: SecretStr = SecretStr("")
    moss_index_name: str = ""
    # "" means unspecified: let Moss adopt the stored index's model on resume
    # (and use its own default for a fresh index) instead of forcing one.
    moss_model_id: str = ""
    moss_top_k: int = Field(default=5, gt=0)
    moss_alpha: float = Field(default=0.8, ge=0.0, le=1.0)
    moss_context_header: str = "Relevant knowledge from Moss:"
    # Cap the injected grounding block; 0 = unlimited.
    moss_max_context_chars: int = Field(default=2000, ge=0)
    enable_moss: bool = True
