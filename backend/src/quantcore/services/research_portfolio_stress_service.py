from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import Mapping

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_construction_service import ResearchPortfolio


@dataclass(frozen=True)
class ResearchStressScenarioDefinition:
    """Versioned deterministic hypothetical return shocks by security.

    ``default_shock`` may be used for broad scenarios such as a market selloff.
    When it is omitted, every held security must have an explicit shock.
    Shocks are one-period return assumptions and must not be below -100%.
    """

    scenario_key: str
    definition_version: str
    shocks_by_security: Mapping[int, float]
    default_shock: float | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_key, str) or not self.scenario_key.strip():
            raise InvalidInputError("Stress scenario key must be a non-empty string.")
        if not isinstance(self.definition_version, str) or not self.definition_version.strip():
            raise InvalidInputError("Stress scenario definition version must be a non-empty string.")
        if not isinstance(self.shocks_by_security, Mapping):
            raise InvalidInputError("Stress scenario shocks_by_security must be a mapping.")
        for security_id, shock in self.shocks_by_security.items():
            if not isinstance(security_id, int) or isinstance(security_id, bool):
                raise InvalidInputError("Stress scenario security IDs must be integers.")
            self._validate_shock(shock, f"Stress shock for security {security_id}")
        if self.default_shock is not None:
            self._validate_shock(self.default_shock, "Stress scenario default_shock")
        if self.description is not None and not isinstance(self.description, str):
            raise InvalidInputError("Stress scenario description must be a string or None.")

        object.__setattr__(self, "scenario_key", self.scenario_key.strip())
        object.__setattr__(self, "definition_version", self.definition_version.strip())
        object.__setattr__(self, "shocks_by_security", MappingProxyType(dict(self.shocks_by_security)))
        if self.description is not None:
            object.__setattr__(self, "description", self.description.strip() or None)

    @property
    def identity(self) -> tuple[str, str]:
        return self.scenario_key, self.definition_version

    @staticmethod
    def _validate_shock(value: object, name: str) -> None:
        if isinstance(value, bool):
            raise InvalidInputError(f"{name} must be a finite numeric return shock.")
        try:
            shock = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(f"{name} must be numeric.") from exc
        if not isfinite(shock) or shock < -1.0:
            raise InvalidInputError(f"{name} must be finite and greater than or equal to -100%.")


@dataclass(frozen=True)
class ResearchPortfolioStressImpact:
    """Deterministic scenario contribution for one portfolio position."""

    security_id: int
    symbol: str
    target_weight: float
    shock: float
    contribution: float


@dataclass(frozen=True)
class ResearchPortfolioStressResult:
    """Immutable hypothetical stress result for one target portfolio."""

    scenario_identity: tuple[str, str]
    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    position_count: int
    shocked_position_count: int
    portfolio_return: float
    portfolio_value: float | None
    pnl_amount: float | None
    stressed_value: float | None
    best_position_contribution: float
    worst_position_contribution: float
    impacts: tuple[ResearchPortfolioStressImpact, ...]


class ResearchPortfolioStressService:
    """Apply deterministic hypothetical return shocks to an existing portfolio.

    This service is a scenario engine, not a forecast or historical backtest. It
    consumes only the target weights and an explicit versioned scenario definition.
    It does not fetch market data, estimate correlations, infer factor betas, or
    mutate portfolio positions.
    """

    def apply(
        self,
        portfolio: ResearchPortfolio,
        scenario: ResearchStressScenarioDefinition,
        portfolio_value: float | None = None,
    ) -> ResearchPortfolioStressResult:
        self._validate_portfolio(portfolio)
        if not isinstance(scenario, ResearchStressScenarioDefinition):
            raise InvalidInputError(
                "Portfolio stress analysis requires a ResearchStressScenarioDefinition."
            )
        if portfolio_value is not None:
            if isinstance(portfolio_value, bool):
                raise InvalidInputError("Portfolio value must be a finite positive number.")
            try:
                value = float(portfolio_value)
            except (TypeError, ValueError) as exc:
                raise InvalidInputError("Portfolio value must be numeric.") from exc
            if not isfinite(value) or value <= 0.0:
                raise InvalidInputError("Portfolio value must be a finite positive number.")
        else:
            value = None

        impacts: list[ResearchPortfolioStressImpact] = []
        for position in sorted(portfolio.positions, key=lambda item: (item.security_id, item.symbol)):
            if position.security_id in scenario.shocks_by_security:
                shock = float(scenario.shocks_by_security[position.security_id])
            elif scenario.default_shock is not None:
                shock = float(scenario.default_shock)
            else:
                raise InvalidInputError(
                    f"Missing stress shock for portfolio security {position.security_id}."
                )
            contribution = float(position.target_weight) * shock
            if not isfinite(contribution):
                raise InvalidInputError("Portfolio stress contribution must be finite.")
            impacts.append(
                ResearchPortfolioStressImpact(
                    security_id=position.security_id,
                    symbol=position.symbol,
                    target_weight=float(position.target_weight),
                    shock=shock,
                    contribution=contribution,
                )
            )

        portfolio_return = sum(impact.contribution for impact in impacts)
        if not isfinite(portfolio_return):
            raise InvalidInputError("Portfolio stress return must be finite.")
        pnl_amount = value * portfolio_return if value is not None else None
        stressed_value = value + pnl_amount if value is not None else None
        if pnl_amount is not None and (not isfinite(pnl_amount) or not isfinite(stressed_value)):
            raise InvalidInputError("Portfolio stress value impact must be finite.")

        contributions = tuple(impact.contribution for impact in impacts)
        return ResearchPortfolioStressResult(
            scenario_identity=scenario.identity,
            strategy_key=portfolio.strategy_key,
            strategy_definition_version=portfolio.strategy_definition_version,
            signal_identity=portfolio.signal_identity,
            as_of=portfolio.as_of,
            position_count=len(impacts),
            shocked_position_count=sum(impact.shock != 0.0 for impact in impacts),
            portfolio_return=portfolio_return,
            portfolio_value=value,
            pnl_amount=pnl_amount,
            stressed_value=stressed_value,
            best_position_contribution=max(contributions, default=0.0),
            worst_position_contribution=min(contributions, default=0.0),
            impacts=tuple(impacts),
        )

    @staticmethod
    def _validate_portfolio(portfolio: ResearchPortfolio) -> None:
        if not isinstance(portfolio, ResearchPortfolio):
            raise InvalidInputError("Portfolio stress analysis requires a ResearchPortfolio.")
        if portfolio.status.name != "CONSTRUCTED":
            raise InvalidInputError(
                "Portfolio stress analysis requires a constructed target portfolio."
            )
        if not isinstance(portfolio.as_of, datetime) or portfolio.as_of.tzinfo is None:
            raise InvalidInputError("Portfolio stress analysis as_of must be timezone-aware.")
        seen: set[int] = set()
        for position in portfolio.positions:
            if position.security_id in seen:
                raise InvalidInputError("Portfolio stress analysis requires unique security IDs.")
            seen.add(position.security_id)
            if position.as_of != portfolio.as_of:
                raise InvalidInputError(
                    "Portfolio position as_of must match the portfolio as_of."
                )
            if not isfinite(float(position.target_weight)):
                raise InvalidInputError("Portfolio position weights must be finite.")
