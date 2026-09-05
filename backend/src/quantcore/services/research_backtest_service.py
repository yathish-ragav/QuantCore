from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Iterable, Mapping, Protocol

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
    ResearchPortfolioConstraintService,
    ResearchPortfolioConstraintStatus,
)
from quantcore.services.research_portfolio_construction_service import ResearchPortfolio
from quantcore.services.research_rebalance_service import (
    ResearchRebalanceDefinition,
    ResearchRebalanceService,
)
from quantcore.services.research_transaction_cost_service import (
    ResearchTransactionCostDefinition,
    ResearchTransactionCostService,
    ResearchTransactionCostResult,
)


class ResearchBacktestPriceObservation(Protocol):
    """Minimum historical price contract required for portfolio valuation."""

    date: datetime
    close: float
    adjusted_close: float | None


class ResearchBacktestStatus(str, Enum):
    """Outcome of one deterministic historical backtest."""

    COMPLETED = "COMPLETED"


class ResearchBacktestPeriodStatus(str, Enum):
    """Outcome of one historical valuation interval."""

    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ResearchBacktestDefinition:
    """Versioned declaration of a weight-based historical portfolio backtest.

    Rebalance timestamps are supplied explicitly by the caller through the target
    portfolio sequence. This definition therefore records the requested interval
    and methodology identities without inventing calendar dates or scheduling.
    """

    backtest_key: str
    definition_version: str
    strategy_identity: tuple[str, str]
    constraint_identity: tuple[str, str]
    rebalance_identity: tuple[str, str]
    transaction_cost_identity: tuple[str, str]
    start_as_of: datetime
    end_as_of: datetime
    initial_capital: float
    price_basis: PriceBasis = PriceBasis.ADJUSTED
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.backtest_key, str) or not self.backtest_key.strip():
            raise InvalidInputError("Backtest key must be a non-empty string.")
        if not isinstance(self.definition_version, str) or not self.definition_version.strip():
            raise InvalidInputError("Backtest definition version must be a non-empty string.")
        self._validate_identity(self.strategy_identity, "strategy_identity")
        self._validate_identity(self.constraint_identity, "constraint_identity")
        self._validate_identity(self.rebalance_identity, "rebalance_identity")
        self._validate_identity(self.transaction_cost_identity, "transaction_cost_identity")

        for value, name in (
            (self.start_as_of, "start_as_of"),
            (self.end_as_of, "end_as_of"),
        ):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise InvalidInputError(f"Backtest {name} must be timezone-aware.")
        if self.start_as_of >= self.end_as_of:
            raise InvalidInputError("Backtest start_as_of must precede end_as_of.")
        if self.start_as_of > datetime.now(timezone.utc):
            raise InvalidInputError("Backtest start_as_of must not be in the future.")
        if self.end_as_of > datetime.now(timezone.utc):
            raise InvalidInputError("Backtest end_as_of must not be in the future.")

        if isinstance(self.initial_capital, bool):
            raise InvalidInputError("Backtest initial_capital must be a finite positive number.")
        try:
            capital = float(self.initial_capital)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError("Backtest initial_capital must be numeric.") from exc
        if not isfinite(capital) or capital <= 0.0:
            raise InvalidInputError("Backtest initial_capital must be a finite positive number.")
        if not isinstance(self.price_basis, PriceBasis):
            raise InvalidInputError("Backtest price_basis must be a valid PriceBasis.")
        if self.description is not None and not isinstance(self.description, str):
            raise InvalidInputError("Backtest description must be a string or None.")

        object.__setattr__(self, "backtest_key", self.backtest_key.strip())
        object.__setattr__(self, "definition_version", self.definition_version.strip())
        object.__setattr__(self, "initial_capital", capital)
        if self.description is not None:
            object.__setattr__(self, "description", self.description.strip() or None)

    @staticmethod
    def _validate_identity(value: object, name: str) -> None:
        if (
            not isinstance(value, tuple)
            or len(value) != 2
            or not all(isinstance(part, str) and part.strip() for part in value)
        ):
            raise InvalidInputError(f"{name} must be a non-empty (key, version) tuple.")

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable backtest definition identity."""
        return self.backtest_key, self.definition_version


@dataclass(frozen=True)
class ResearchBacktestPeriod:
    """Immutable result for one interval between explicit portfolio boundaries."""

    period_start: datetime
    period_end: datetime
    starting_equity: float
    ending_equity: float
    gross_return: float
    transaction_cost_fraction: float
    net_return: float
    turnover: float
    status: ResearchBacktestPeriodStatus


@dataclass(frozen=True)
class ResearchBacktest:
    """Immutable deterministic historical backtest result."""

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
    periods: tuple[ResearchBacktestPeriod, ...]
    status: ResearchBacktestStatus


class ResearchBacktestService:
    """Run a deterministic weight-based historical backtest.

    The first target portfolio establishes the initial allocation. Each later
    target is treated as the next explicit rebalance boundary. Returns are valued
    from the first available price strictly after the period start to the first
    available price strictly after the period end, preserving the information
    boundary used elsewhere in QuantCore. Successive target weights define the
    rebalance turnover; this first backtest version does not model intra-period
    weight drift or executable share-level fills.
    """

    def __init__(self) -> None:
        self._constraint_service = ResearchPortfolioConstraintService()
        self._rebalance_service = ResearchRebalanceService()
        self._transaction_cost_service = ResearchTransactionCostService()

    def run(
        self,
        definition: ResearchBacktestDefinition,
        target_portfolios: Iterable[ResearchPortfolio],
        price_history_by_security: Mapping[int, Iterable[ResearchBacktestPriceObservation]],
        constraint_definition: ResearchPortfolioConstraintDefinition,
        rebalance_definition: ResearchRebalanceDefinition,
        transaction_cost_definition: ResearchTransactionCostDefinition,
    ) -> ResearchBacktest:
        self._validate_inputs(
            definition,
            target_portfolios,
            price_history_by_security,
            constraint_definition,
            rebalance_definition,
            transaction_cost_definition,
        )

        targets = tuple(target_portfolios)
        periods: list[ResearchBacktestPeriod] = []
        equity = definition.initial_capital

        for target in targets:
            if target.status.name != "CONSTRUCTED":
                raise InvalidInputError(
                    f"Backtest requires constructed target portfolios; "
                    f"received {target.status.name} at {target.as_of.isoformat()}."
                )
            constraint_result = self._constraint_service.validate(
                target,
                constraint_definition,
            )
            if constraint_result.status is not ResearchPortfolioConstraintStatus.PASSED:
                raise InvalidInputError(
                    f"Backtest target portfolio at {target.as_of.isoformat()} violates portfolio constraints."
                )

        for previous, target in zip(targets, targets[1:]):
            rebalance = self._rebalance_service.rebalance(
                previous,
                target,
                rebalance_definition,
                target.as_of,
            )
            transaction_cost = self._transaction_cost_service.calculate(
                rebalance,
                transaction_cost_definition,
            )

            gross_return = self._period_return(
                previous,
                previous.as_of,
                target.as_of,
                price_history_by_security,
                definition.price_basis,
            )
            ending_equity_before_cost = equity * (1.0 + gross_return)
            if not isfinite(ending_equity_before_cost) or ending_equity_before_cost <= 0.0:
                raise InvalidInputError(
                    "Backtest equity must remain finite and positive after gross returns."
                )

            net_return = (
                (1.0 + gross_return)
                * (1.0 - transaction_cost.cost_fraction)
                - 1.0
            )
            ending_equity = equity * (1.0 + net_return)
            if not isfinite(net_return) or not isfinite(ending_equity) or ending_equity <= 0.0:
                raise InvalidInputError(
                    "Backtest equity must remain finite and positive after transaction costs."
                )

            periods.append(
                ResearchBacktestPeriod(
                    period_start=previous.as_of,
                    period_end=target.as_of,
                    starting_equity=equity,
                    ending_equity=ending_equity,
                    gross_return=gross_return,
                    transaction_cost_fraction=transaction_cost.cost_fraction,
                    net_return=net_return,
                    turnover=transaction_cost.turnover,
                    status=ResearchBacktestPeriodStatus.COMPLETED,
                )
            )
            equity = ending_equity

        total_return = equity / definition.initial_capital - 1.0
        if not isfinite(total_return):
            raise InvalidInputError("Backtest total return must be finite.")

        return ResearchBacktest(
            backtest_key=definition.backtest_key,
            backtest_definition_version=definition.definition_version,
            strategy_identity=definition.strategy_identity,
            constraint_identity=definition.constraint_identity,
            rebalance_identity=definition.rebalance_identity,
            transaction_cost_identity=definition.transaction_cost_identity,
            start_as_of=definition.start_as_of,
            end_as_of=definition.end_as_of,
            initial_capital=definition.initial_capital,
            final_equity=equity,
            total_return=total_return,
            price_basis=definition.price_basis,
            periods=tuple(periods),
            status=ResearchBacktestStatus.COMPLETED,
        )

    @classmethod
    def _period_return(
        cls,
        portfolio: ResearchPortfolio,
        period_start: datetime,
        period_end: datetime,
        price_history_by_security: Mapping[int, Iterable[ResearchBacktestPriceObservation]],
        price_basis: PriceBasis,
    ) -> float:
        portfolio_return = 0.0
        for position in portfolio.positions:
            prices = cls._normalize_price_history(
                price_history_by_security.get(position.security_id, ()),
                position.security_id,
            )
            start = cls._first_after(prices, period_start)
            end = cls._first_after(prices, period_end)
            if start is None or end is None:
                raise InvalidInputError(
                    f"Missing historical price for security {position.security_id} "
                    f"across period {period_start.isoformat()} to {period_end.isoformat()}."
                )
            start_price = cls._select_price(start, price_basis)
            end_price = cls._select_price(end, price_basis)
            if start_price <= 0.0 or end_price <= 0.0:
                raise InvalidInputError("Backtest prices must be strictly positive.")
            security_return = end_price / start_price - 1.0
            contribution = float(position.target_weight) * security_return
            if not isfinite(contribution):
                raise InvalidInputError("Backtest portfolio return must be finite.")
            portfolio_return += contribution

        if not isfinite(portfolio_return):
            raise InvalidInputError("Backtest portfolio return must be finite.")
        return portfolio_return

    @staticmethod
    def _first_after(
        prices: tuple[ResearchBacktestPriceObservation, ...],
        boundary: datetime,
    ) -> ResearchBacktestPriceObservation | None:
        for observation in prices:
            if observation.date > boundary:
                return observation
        return None

    @staticmethod
    def _select_price(
        observation: ResearchBacktestPriceObservation,
        price_basis: PriceBasis,
    ) -> float:
        if price_basis is PriceBasis.UNADJUSTED:
            value = observation.close
        else:
            value = observation.adjusted_close
            if value is None:
                raise InvalidInputError(
                    "Adjusted-price backtests require adjusted_close for every valuation observation."
                )
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError("Backtest prices must be numeric.") from exc
        if not isfinite(numeric):
            raise InvalidInputError("Backtest prices must be finite.")
        return numeric

    @staticmethod
    def _normalize_price_history(
        observations: Iterable[ResearchBacktestPriceObservation],
        security_id: int,
    ) -> tuple[ResearchBacktestPriceObservation, ...]:
        try:
            values = tuple(observations)
        except TypeError as exc:
            raise InvalidInputError(
                f"Price history for security {security_id} must be iterable."
            ) from exc
        seen_dates: set[datetime] = set()
        normalized: list[ResearchBacktestPriceObservation] = []
        for observation in values:
            date = getattr(observation, "date", None)
            if not isinstance(date, datetime) or date.tzinfo is None:
                raise InvalidInputError(
                    "Backtest price observation dates must be timezone-aware."
                )
            if date in seen_dates:
                raise InvalidInputError(
                    f"Price history for security {security_id} contains duplicate dates."
                )
            seen_dates.add(date)
            for field in ("close", "adjusted_close"):
                value = getattr(observation, field, None)
                if value is not None:
                    try:
                        numeric = float(value)
                    except (TypeError, ValueError) as exc:
                        raise InvalidInputError(
                            f"Backtest price observation {field} must be numeric."
                        ) from exc
                    if not isfinite(numeric):
                        raise InvalidInputError(
                            f"Backtest price observation {field} must be finite."
                        )
            normalized.append(observation)
        normalized.sort(key=lambda item: item.date)
        return tuple(normalized)

    @classmethod
    def _validate_inputs(
        cls,
        definition: ResearchBacktestDefinition,
        target_portfolios: Iterable[ResearchPortfolio],
        price_history_by_security: Mapping[int, Iterable[ResearchBacktestPriceObservation]],
        constraint_definition: ResearchPortfolioConstraintDefinition,
        rebalance_definition: ResearchRebalanceDefinition,
        transaction_cost_definition: ResearchTransactionCostDefinition,
    ) -> None:
        if not isinstance(definition, ResearchBacktestDefinition):
            raise InvalidInputError(
                "Backtest requires a ResearchBacktestDefinition."
            )
        try:
            targets = tuple(target_portfolios)
        except TypeError as exc:
            raise InvalidInputError("Backtest target portfolios must be iterable.") from exc
        if len(targets) < 2:
            raise InvalidInputError("Backtest requires at least two target portfolio boundaries.")
        if not isinstance(price_history_by_security, Mapping):
            raise InvalidInputError("Backtest price history must be keyed by security ID.")
        if not isinstance(
            constraint_definition,
            ResearchPortfolioConstraintDefinition,
        ):
            raise InvalidInputError(
                "Backtest requires a ResearchPortfolioConstraintDefinition."
            )
        if not isinstance(rebalance_definition, ResearchRebalanceDefinition):
            raise InvalidInputError(
                "Backtest requires a ResearchRebalanceDefinition."
            )
        if not isinstance(
            transaction_cost_definition,
            ResearchTransactionCostDefinition,
        ):
            raise InvalidInputError(
                "Backtest requires a ResearchTransactionCostDefinition."
            )
        if constraint_definition.identity != definition.constraint_identity:
            raise InvalidInputError("Backtest constraint identity does not match its definition.")
        if rebalance_definition.identity != definition.rebalance_identity:
            raise InvalidInputError("Backtest rebalance identity does not match its definition.")
        if transaction_cost_definition.identity != definition.transaction_cost_identity:
            raise InvalidInputError(
                "Backtest transaction-cost identity does not match its definition."
            )

        now = datetime.now(timezone.utc)
        seen_dates: set[datetime] = set()
        for target in targets:
            if not isinstance(target, ResearchPortfolio):
                raise InvalidInputError(
                    "Backtest target portfolios must use the ResearchPortfolio contract."
                )
            if target.as_of in seen_dates:
                raise InvalidInputError(
                    "Backtest target portfolios must not contain duplicate as_of values."
                )
            seen_dates.add(target.as_of)
            if target.as_of.tzinfo is None:
                raise InvalidInputError("Backtest target portfolio as_of must be timezone-aware.")
            if target.as_of < definition.start_as_of or target.as_of > definition.end_as_of:
                raise InvalidInputError(
                    "Backtest target portfolio as_of values must lie within the definition interval."
                )
            if target.as_of > now:
                raise InvalidInputError("Backtest target portfolio as_of must not be in the future.")
            if (target.strategy_key, target.strategy_definition_version) != definition.strategy_identity:
                raise InvalidInputError(
                    "Backtest target portfolio strategy identity does not match the definition."
                )

        ordered_dates = sorted(seen_dates)
        if ordered_dates[0] != definition.start_as_of or ordered_dates[-1] != definition.end_as_of:
            raise InvalidInputError(
                "Backtest target portfolio boundaries must equal start_as_of and end_as_of."
            )
        if tuple(target.as_of for target in targets) != tuple(ordered_dates):
            raise InvalidInputError(
                "Backtest target portfolios must be supplied in ascending as_of order."
            )

        for target in targets:
            for position in target.positions:
                if not isinstance(position.security_id, int) or isinstance(position.security_id, bool):
                    raise InvalidInputError("Backtest portfolio security IDs must be integers.")
                if not isfinite(float(position.target_weight)):
                    raise InvalidInputError("Backtest portfolio weights must be finite.")
