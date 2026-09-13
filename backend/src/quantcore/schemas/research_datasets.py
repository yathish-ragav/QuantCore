from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


ResearchSymbols = Annotated[list[str], Field(min_length=1, max_length=100)]
ResearchAsOfs = Annotated[list[datetime], Field(min_length=1, max_length=50)]
ResearchDefinitionIdentities = Annotated[
    list[tuple[str, str]],
    Field(min_length=1, max_length=32),
]


class ResearchHistoricalDatasetRequest(BaseModel):
    """Bounded request for a deterministic PIT historical research dataset."""

    symbols: ResearchSymbols
    as_ofs: ResearchAsOfs
    definition_identities: ResearchDefinitionIdentities | None = None
    dataset_identity: tuple[str, str] | None = None


class ResearchHistoricalDatasetRowResponse(BaseModel):
    """One PIT row in a historical research dataset."""

    symbol: str
    security_id: int
    as_of: datetime
    feature_vector: dict


class ResearchHistoricalDatasetResponse(BaseModel):
    """Stable API projection of a deterministic historical research dataset."""

    dataset_fingerprint: str
    definition_identities: list[tuple[str, str]] | None
    dataset_identity: tuple[str, str] | None
    row_count: int
    rows: list[ResearchHistoricalDatasetRowResponse]
