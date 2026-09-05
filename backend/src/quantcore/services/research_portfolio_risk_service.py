from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_construction_service import ResearchPortfolio


@dataclass(frozen=True)
class ResearchPortfolioRiskSnapshot:
    """Deterministic descriptive risk snapshot for an existing target portfolio."""

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


class ResearchPortfolioRiskService:
    """Compute descriptive exposure and concentration metrics from a target portfolio."""

    def snapshot(self, portfolio: ResearchPortfolio) -> ResearchPortfolioRiskSnapshot:
        self._validate(portfolio)
        positions = tuple(portfolio.positions)
        weights = tuple(float(position.target_weight) for position in positions)
        long_weights = tuple(weight for weight in weights if weight > 0.0)
        short_weights = tuple(abs(weight) for weight in weights if weight < 0.0)

        gross = sum(abs(weight) for weight in weights)
        net = sum(weights)
        long_exposure = sum(long_weights)
        short_exposure = sum(short_weights)
        max_abs = max((abs(weight) for weight in weights), default=0.0)

        hhi = self._hhi(weights, gross)
        long_hhi = self._hhi(long_weights, long_exposure)
        short_hhi = self._hhi(short_weights, short_exposure)

        return ResearchPortfolioRiskSnapshot(
            strategy_key=portfolio.strategy_key,
            strategy_definition_version=portfolio.strategy_definition_version,
            signal_identity=portfolio.signal_identity,
            as_of=portfolio.as_of,
            position_count=len(positions),
            long_count=len(long_weights),
            short_count=len(short_weights),
            gross_exposure=gross,
            net_exposure=net,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            max_abs_position_weight=max_abs,
            net_to_gross_exposure=(abs(net) / gross if gross else 0.0),
            hhi=hhi,
            effective_position_count=(1.0 / hhi if hhi else 0.0),
            long_hhi=long_hhi,
            long_effective_position_count=(1.0 / long_hhi if long_hhi else 0.0),
            short_hhi=short_hhi,
            short_effective_position_count=(1.0 / short_hhi if short_hhi else 0.0),
        )

    @staticmethod
    def _hhi(weights: tuple[float, ...], exposure: float) -> float:
        if not exposure:
            return 0.0
        shares = tuple(weight / exposure for weight in weights)
        return sum(share * share for share in shares)

    @staticmethod
    def _validate(portfolio: ResearchPortfolio) -> None:
        if not isinstance(portfolio, ResearchPortfolio):
            raise InvalidInputError("Portfolio risk requires a ResearchPortfolio.")
        if portfolio.status.name != "CONSTRUCTED":
            raise InvalidInputError(
                f"Portfolio risk requires constructed target portfolios; received {portfolio.status.name}."
            )
        for position in portfolio.positions:
            if not isfinite(float(position.target_weight)):
                raise InvalidInputError("Portfolio position weights must be finite.")
