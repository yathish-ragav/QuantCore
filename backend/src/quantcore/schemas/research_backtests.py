from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from quantcore.core.enums import PriceBasis
from quantcore.schemas.research_portfolios import (
    ResearchPortfolioPositionResponse,
    ResearchPortfolioStrategyRequest,
)
from quantcore.schemas.research_signals import ResearchSignalFactorRequest
from quantcore.services.research_rebalance_service import ResearchRebalanceFrequency
from quantcore.services.research_strategy_service import ResearchStrategyDirection


class ResearchBacktestRequest(BaseModel):
    """Bounded request for deterministic historical portfolio backtesting."""

    symbols: list[str] = Field(min_length=1, max_length=100)
    as_ofs: list[datetime] = Field(min_length=2, max_length=50)
    definition_identities: list[tuple[str, str]] | None = Field(
        default=None, min_length=1, max_length=32
    )
    dataset_identity: tuple[str, str] | None = None

    signal_key: str = Field(min_length=1, max_length=100)
    signal_definition_version: str = Field(min_length=1, max_length=100)
    signal_description: str | None = Field(default=None, max_length=500)
    factors: list[ResearchSignalFactorRequest] = Field(min_length=1, max_length=16)
    strategy: ResearchPortfolioStrategyRequest

    backtest_key: str = Field(min_length=1, max_length=100)
    backtest_definition_version: str = Field(min_length=1, max_length=100)
    initial_capital: float = Field(gt=0.0)
    price_basis: PriceBasis = PriceBasis.ADJUSTED
    backtest_description: str | None = Field(default=None, max_length=500)

    constraint_key: str = Field(min_length=1, max_length=100)
    constraint_definition_version: str = Field(min_length=1, max_length=100)
    max_position_weight: float | None = None
    max_gross_exposure: float | None = None
    min_net_exposure: float | None = None
    max_net_exposure: float | None = None
    max_long_exposure: float | None = None
    max_short_exposure: float | None = None
    constraint_description: str | None = Field(default=None, max_length=500)

    rebalance_key: str = Field(min_length=1, max_length=100)
    rebalance_definition_version: str = Field(min_length=1, max_length=100)
    frequency: ResearchRebalanceFrequency
    rebalance_description: str | None = Field(default=None, max_length=500)

    cost_key: str = Field(min_length=1, max_length=100)
    cost_definition_version: str = Field(min_length=1, max_length=100)
    one_way_cost_bps: float = Field(ge=0.0)
    cost_description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_interval(self):
        if any(value.tzinfo is None for value in self.as_ofs):
            raise ValueError("as_ofs must be timezone-aware")
        if tuple(self.as_ofs) != tuple(sorted(self.as_ofs)):
            raise ValueError("as_ofs must be supplied in ascending order")
        if len(set(self.as_ofs)) != len(self.as_ofs):
            raise ValueError("as_ofs must not contain duplicates")
        return self


class ResearchBacktestPeriodResponse(BaseModel):
    """Stable API projection of one completed backtest period."""

    period_start: datetime
    period_end: datetime
    starting_equity: float
    ending_equity: float
    gross_return: float
    transaction_cost_fraction: float
    net_return: float
    turnover: float
    status: str


class ResearchBacktestTargetPortfolioResponse(BaseModel):
    """Portfolio boundary plus its deterministic dataset provenance."""

    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    status: str
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


class ResearchBacktestResponse(BaseModel):
    """Stable API projection of a deterministic historical backtest."""

    backtest_key: str
    backtest_definition_version: str
    strategy_identity: tuple[str, str]
    constraint_identity: tuple[str, str]
    rebalance_identity: tuple[str, str]
    transaction_cost_identity: tuple[str, str]
    start_as_of: datetime
    end_as_of: datetime
    initial_capital: float
    final_equity: float
    total_return: float
    price_basis: PriceBasis
    status: str
    periods: list[ResearchBacktestPeriodResponse]
    target_portfolios: list[ResearchBacktestTargetPortfolioResponse]


class ResearchBacktestPerformanceProvenanceResponse(BaseModel):
    """Dataset provenance for one target portfolio used by performance analysis."""

    as_of: datetime
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None


class ResearchBacktestPerformanceResponse(BaseModel):
    """Stable API projection of deterministic realized backtest performance."""

    backtest_key: str
    backtest_definition_version: str
    strategy_identity: tuple[str, str]
    constraint_identity: tuple[str, str]
    rebalance_identity: tuple[str, str]
    transaction_cost_identity: tuple[str, str]
    start_as_of: datetime
    end_as_of: datetime
    initial_capital: float
    final_equity: float
    total_return: float
    price_basis: PriceBasis
    period_count: int
    annualized_return: float
    annualized_volatility: float
    maximum_drawdown: float
    maximum_drawdown_duration_days: float
    average_period_return: float
    winning_periods: int
    losing_periods: int
    flat_periods: int
    win_rate: float
    average_turnover: float
    target_portfolios: list[ResearchBacktestPerformanceProvenanceResponse]
