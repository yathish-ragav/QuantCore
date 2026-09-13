from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from quantcore.core.enums import PriceBasis


class ResearchFactorReturnMethodologyRequest(BaseModel):
    """Bounded request for a deterministic cross-sectional factor-return series."""

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
    bucket_count: int = Field(ge=2, le=50)
    minimum_observations_per_leg: int = Field(ge=1, le=100)


class ResearchFactorReturnBucketResponse(BaseModel):
    """One equal-weighted rank bucket in a factor-return slice."""

    bucket_number: int
    observation_count: int
    eligible_return_count: int
    mean_forward_return: float | None


class ResearchFactorReturnSliceResponse(BaseModel):
    """One cross-sectional factor-return observation at one as-of point."""

    as_of: datetime
    total_observation_count: int
    eligible_observation_count: int
    long_bucket: int
    short_bucket: int
    long_return: float | None
    short_return: float | None
    long_short_return: float | None
    status: str
    buckets: list[ResearchFactorReturnBucketResponse]


class ResearchFactorReturnMethodologyResponse(BaseModel):
    """Stable API projection of a deterministic factor-return series."""

    factor_key: str
    definition_version: str
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    horizon: int
    return_price_basis: PriceBasis
    bucket_count: int
    weighting: str
    long_bucket: int
    short_bucket: int
    construction: str
    row_count: int
    slices: list[ResearchFactorReturnSliceResponse]
