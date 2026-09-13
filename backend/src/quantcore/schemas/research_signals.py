from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResearchSignalFactorRequest(BaseModel):
    """One versioned factor input and its signal-construction policy."""

    factor_key: str = Field(min_length=1, max_length=100)
    definition_version: str = Field(min_length=1, max_length=100)
    weight: float = Field(gt=0.0, le=1.0)
    higher_is_better: bool = True


class ResearchSignalRequest(BaseModel):
    """Bounded request for deterministic composite research-signal construction."""

    symbols: list[str] = Field(min_length=1, max_length=100)
    as_ofs: list[datetime] = Field(min_length=1, max_length=50)
    definition_identities: list[tuple[str, str]] | None = Field(
        default=None, min_length=1, max_length=32
    )
    dataset_identity: tuple[str, str] | None = None
    signal_key: str = Field(min_length=1, max_length=100)
    signal_definition_version: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    factors: list[ResearchSignalFactorRequest] = Field(min_length=1, max_length=16)


class ResearchSignalContributionResponse(BaseModel):
    """One factor contribution to a composite signal observation."""

    factor_key: str
    definition_version: str
    normalized_rank: float
    weight: float
    weighted_contribution: float


class ResearchSignalRowResponse(BaseModel):
    """One composite research signal observation."""

    symbol: str
    security_id: int
    as_of: datetime
    score: float
    centered_score: float
    contributions: list[ResearchSignalContributionResponse]


class ResearchSignalFactorResponse(BaseModel):
    """Factor policy included in the product response for reproducibility."""

    factor_key: str
    definition_version: str
    weight: float
    higher_is_better: bool


class ResearchSignalResponse(BaseModel):
    """Stable API projection of a deterministic composite research signal."""

    signal_key: str
    definition_version: str
    description: str | None
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    factor_count: int
    factors: list[ResearchSignalFactorResponse]
    construction: str
    row_count: int
    rows: list[ResearchSignalRowResponse]
