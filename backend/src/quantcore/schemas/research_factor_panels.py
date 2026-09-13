from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResearchFactorPanelRequest(BaseModel):
    """Bounded request for a deterministic PIT factor panel."""

    symbols: list[str] = Field(min_length=1, max_length=100)
    as_ofs: list[datetime] = Field(min_length=1, max_length=50)
    definition_identities: list[tuple[str, str]] | None = Field(
        default=None, min_length=1, max_length=32
    )
    dataset_identity: tuple[str, str] | None = None
    factor_key: str = Field(min_length=1, max_length=100)
    factor_definition_version: str = Field(min_length=1, max_length=100)


class ResearchFactorPanelRowResponse(BaseModel):
    """One PIT factor value in a historical factor panel."""

    symbol: str
    security_id: int
    as_of: datetime
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    input_manifest: dict[str, Any] | None


class ResearchFactorPanelResponse(BaseModel):
    """Stable API projection of a deterministic PIT factor panel."""

    factor_key: str
    definition_version: str
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    unit: str | None
    row_count: int
    rows: list[ResearchFactorPanelRowResponse]
