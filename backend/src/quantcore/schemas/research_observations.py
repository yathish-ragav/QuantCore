from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

ResearchDefinitionIdentity = tuple[str, str]


class ResearchObservationMaterializationRequest(BaseModel):
    """Bounded request to materialize canonical PIT research observations."""

    symbol: Annotated[str, Field(min_length=1, max_length=32)]
    as_of: datetime
    definition_identities: list[ResearchDefinitionIdentity] | None = Field(
        default=None,
        min_length=1,
        max_length=32,
    )
    macro_series_ids: list[str] = Field(default_factory=list, max_length=32)


class ResearchObservationMaterializedResponse(BaseModel):
    """Stable API projection of one newly materialized observation."""

    symbol: str
    observation_key: str
    definition_version: str
    as_of: datetime
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    input_manifest: dict
    input_fingerprint: str


class ResearchObservationMaterializationResponse(BaseModel):
    """Result of one atomic PIT observation-materialization request."""

    symbol: str
    as_of: datetime
    materialized_count: int
    observations: list[ResearchObservationMaterializedResponse]
