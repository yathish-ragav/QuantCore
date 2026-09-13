from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from quantcore.core.enums import PriceBasis


class ResearchFactorReturnRequest(BaseModel):
    """Bounded request for deterministic factor forward-return outcomes."""

    symbols: list[str] = Field(min_length=1, max_length=100)
    as_ofs: list[datetime] = Field(min_length=1, max_length=50)
    definition_identities: list[tuple[str, str]] | None = Field(
        default=None, min_length=1, max_length=32
    )
    dataset_identity: tuple[str, str] | None = None
    factor_key: str = Field(min_length=1, max_length=100)
    factor_definition_version: str = Field(min_length=1, max_length=100)
    horizon: int = Field(ge=1, le=252)
    higher_is_better: bool = True
    return_price_basis: PriceBasis = PriceBasis.ADJUSTED


class ResearchFactorReturnRowResponse(BaseModel):
    """One factor observation aligned with its realized forward return."""

    symbol: str
    security_id: int
    factor_as_of: datetime
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    input_manifest: dict[str, Any] | None
    factor_rank: float
    normalized_rank: float
    entry_date: datetime | None
    exit_date: datetime | None
    entry_price: float | None
    exit_price: float | None
    forward_return: float | None
    return_price_basis: PriceBasis
    status: str


class ResearchFactorReturnResponse(BaseModel):
    """Stable API projection of deterministic factor forward returns."""

    factor_key: str
    definition_version: str
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    horizon: int
    return_price_basis: PriceBasis
    entry_policy: str
    ranking: str
    higher_is_better: bool
    row_count: int
    rows: list[ResearchFactorReturnRowResponse]
