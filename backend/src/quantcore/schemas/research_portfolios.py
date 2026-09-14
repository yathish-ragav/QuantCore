from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from quantcore.schemas.research_signals import ResearchSignalFactorRequest
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolioConstructionStatus,
    ResearchPortfolioPositionSide,
)
from quantcore.services.research_rebalance_service import (
    ResearchRebalanceActionType,
    ResearchRebalanceFrequency,
)
from quantcore.services.research_strategy_service import ResearchStrategyDirection


class ResearchPortfolioStrategyRequest(BaseModel):
    """Declarative strategy contract used for one portfolio construction."""

    strategy_key: str = Field(min_length=1, max_length=100)
    definition_version: str = Field(min_length=1, max_length=100)
    signal_identity: tuple[str, str]
    direction: ResearchStrategyDirection
    long_threshold: float | None = None
    short_threshold: float | None = None
    description: str | None = Field(default=None, max_length=500)


class ResearchPortfolioRequest(BaseModel):
    """Bounded request for deterministic target portfolio construction."""

    symbols: list[str] = Field(min_length=1, max_length=100)
    as_ofs: list[datetime] = Field(min_length=1, max_length=50)
    target_as_of: datetime
    definition_identities: list[tuple[str, str]] | None = Field(
        default=None, min_length=1, max_length=32
    )
    dataset_identity: tuple[str, str] | None = None
    signal_key: str = Field(min_length=1, max_length=100)
    signal_definition_version: str = Field(min_length=1, max_length=100)
    signal_description: str | None = Field(default=None, max_length=500)
    factors: list[ResearchSignalFactorRequest] = Field(min_length=1, max_length=16)
    strategy: ResearchPortfolioStrategyRequest

    @model_validator(mode="after")
    def validate_target_as_of(self):
        if any(value.tzinfo is None for value in self.as_ofs) or self.target_as_of.tzinfo is None:
            raise ValueError("as_ofs and target_as_of must be timezone-aware")
        if self.target_as_of not in self.as_ofs:
            raise ValueError("target_as_of must be one of the requested as_ofs")
        return self


class ResearchPortfolioPositionResponse(BaseModel):
    """One deterministic target portfolio position."""

    symbol: str
    security_id: int
    as_of: datetime
    signal_score: float
    side: ResearchPortfolioPositionSide
    target_weight: float


class ResearchPortfolioResponse(BaseModel):
    """Stable API projection of a deterministic target research portfolio."""

    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    status: ResearchPortfolioConstructionStatus
    construction: str
    eligible_count: int
    long_count: int
    short_count: int
    gross_exposure: float
    net_exposure: float
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    signal_construction: str
    positions: list[ResearchPortfolioPositionResponse]


class ResearchPortfolioRiskResponse(BaseModel):
    """Stable API projection of descriptive risk for a target portfolio."""

    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    position_count: int
    long_count: int
    short_count: int
    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    max_abs_position_weight: float
    net_to_gross_exposure: float
    hhi: float
    effective_position_count: float
    long_hhi: float
    long_effective_position_count: float
    short_hhi: float
    short_effective_position_count: float
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    signal_construction: str


class ResearchPortfolioFactorExposureResponse(BaseModel):
    """One deterministic rank-based factor exposure for a target portfolio."""

    factor_identity: tuple[str, str]
    as_of: datetime
    position_count: int
    factor_observation_count: int
    exposure: float
    long_exposure: float
    short_exposure: float
    gross_factor_exposure: float
    gross_normalized_exposure: float


class ResearchPortfolioFactorRiskResponse(BaseModel):
    """Stable API projection of rank-based factor exposures."""

    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    position_count: int
    factor_exposures: list[ResearchPortfolioFactorExposureResponse]
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    signal_construction: str



class ResearchPortfolioConstraintRequest(ResearchPortfolioRequest):
    """Bounded request for validating a constructed research portfolio against explicit constraints."""

    constraint_key: str = Field(min_length=1, max_length=100)
    constraint_definition_version: str = Field(min_length=1, max_length=100)
    max_position_weight: float | None = None
    max_gross_exposure: float | None = None
    min_net_exposure: float | None = None
    max_net_exposure: float | None = None
    max_long_exposure: float | None = None
    max_short_exposure: float | None = None
    constraint_description: str | None = Field(default=None, max_length=500)


class ResearchPortfolioConstraintViolationResponse(BaseModel):
    """Stable API projection of one portfolio constraint violation."""

    constraint: str
    observed_value: float
    limit: float


class ResearchPortfolioConstraintResponse(BaseModel):
    """Stable API projection of deterministic portfolio constraint validation."""

    constraint_key: str
    constraint_definition_version: str
    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    signal_construction: str
    status: str
    violations: list[ResearchPortfolioConstraintViolationResponse]
    observed_max_position_weight: float
    observed_gross_exposure: float
    observed_net_exposure: float
    observed_long_exposure: float
    observed_short_exposure: float


class ResearchPortfolioRebalanceRequest(ResearchPortfolioRequest):
    """Bounded request for deterministic portfolio transition analysis."""

    current_as_of: datetime
    rebalance_key: str = Field(min_length=1, max_length=100)
    rebalance_definition_version: str = Field(min_length=1, max_length=100)
    frequency: ResearchRebalanceFrequency
    rebalance_description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_rebalance_points(self):
        if self.current_as_of.tzinfo is None:
            raise ValueError("current_as_of must be timezone-aware")
        if self.current_as_of >= self.target_as_of:
            raise ValueError("current_as_of must precede target_as_of")
        if self.current_as_of not in self.as_ofs:
            raise ValueError("current_as_of must be one of the requested as_ofs")
        return self


class ResearchPortfolioRebalanceActionResponse(BaseModel):
    """One deterministic target-weight transition."""

    symbol: str
    security_id: int
    current_weight: float
    target_weight: float
    weight_delta: float
    action: ResearchRebalanceActionType


class ResearchPortfolioRebalanceResponse(BaseModel):
    """Stable API projection of deterministic portfolio rebalance analysis."""

    rebalance_key: str
    rebalance_definition_version: str
    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    frequency: ResearchRebalanceFrequency
    current_as_of: datetime
    as_of: datetime
    current_dataset_fingerprint: str
    current_dataset_identity: tuple[str, str] | None
    target_dataset_fingerprint: str
    target_dataset_identity: tuple[str, str] | None
    signal_construction: str
    current_gross_exposure: float
    current_net_exposure: float
    target_gross_exposure: float
    target_net_exposure: float
    turnover: float
    status: str
    actions: list[ResearchPortfolioRebalanceActionResponse]
