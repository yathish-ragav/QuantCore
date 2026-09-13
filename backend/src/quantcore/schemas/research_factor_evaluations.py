from datetime import datetime

from pydantic import BaseModel, Field


class ResearchFactorEvaluationRequest(BaseModel):
    """Bounded request for deterministic cross-sectional factor diagnostics."""

    symbols: list[str] = Field(min_length=1, max_length=100)
    as_ofs: list[datetime] = Field(min_length=1, max_length=50)
    definition_identities: list[tuple[str, str]] | None = Field(
        default=None, min_length=1, max_length=32
    )
    dataset_identity: tuple[str, str] | None = None
    factor_key: str = Field(min_length=1, max_length=100)
    factor_definition_version: str = Field(min_length=1, max_length=100)
    higher_is_better: bool = True


class ResearchFactorEvaluationSliceResponse(BaseModel):
    """Cross-sectional factor diagnostics for one as-of point."""

    as_of: datetime
    observation_count: int
    mean_value: float
    median_value: float
    stddev_value: float
    minimum_value: float
    maximum_value: float
    range_value: float


class ResearchFactorEvaluationResponse(BaseModel):
    """Stable API projection of deterministic factor evaluation diagnostics."""

    factor_key: str
    definition_version: str
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    cross_section_count: int
    total_observation_count: int
    minimum_cross_section_size: int
    maximum_cross_section_size: int
    mean_cross_section_size: float
    mean_cross_section_value: float
    mean_cross_section_stddev: float
    mean_cross_section_range: float
    row_count: int
    cross_sections: list[ResearchFactorEvaluationSliceResponse]
