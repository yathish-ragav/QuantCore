from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Mapping

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_service import (
    ResearchBacktest,
    ResearchBacktestPriceObservation,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionStatus,
)


@dataclass(frozen=True)
class ResearchBacktestPositionAttribution:
    """Realized gross-return contribution of one position for one period."""

    period_start: datetime
    period_end: datetime
    symbol: str
    security_id: int
    target_weight: float
    security_return: float
    gross_contribution: float
    return_contribution: float


@dataclass(frozen=True)
class ResearchBacktestPeriodAttribution:
    """Return attribution for one completed backtest period."""

    period_start: datetime
    period_end: datetime
    starting_equity: float
    ending_equity: float
    gross_return: float
    transaction_cost_drag: float
    net_return: float
    long_contribution: float
    short_contribution: float
    return_contribution: float
    transaction_cost_return_contribution: float
    position_contributions: tuple[ResearchBacktestPositionAttribution, ...]


@dataclass(frozen=True)
class ResearchBacktestAttribution:
    """Deterministic realized-return attribution for a completed backtest."""

    backtest_identity: tuple[str, str]
    periods: tuple[ResearchBacktestPeriodAttribution, ...]
    total_gross_return: float
    total_transaction_cost_drag: float
    total_net_return: float
    total_long_contribution: float
    total_short_contribution: float
    total_transaction_cost_return_contribution: float


class ResearchBacktestAttributionService:
    """Attribute realized backtest returns to positions and transaction costs.

    Position contributions are calculated from the same target weights and
    valuation prices used by `ResearchBacktestService`. They sum to each
    period's gross return. Period contributions are capital-scaled to the
    backtest's initial capital, making the total attribution additive to the
    realized net return. Transaction-cost drag is the exact period difference
    between recorded net and gross returns; no per-security cost allocation is
    invented.

    `total_gross_return` and `total_transaction_cost_drag` are additive
    contributions expressed relative to initial capital, not compounded
    standalone performance series.

    This service does not forecast returns, optimize weights, or infer
    causality. It reports realized historical contribution only.
    """

    def attribute(
        self,
        backtest: ResearchBacktest,
        target_portfolios: tuple[ResearchPortfolio, ...],
        price_history_by_security: Mapping[int, tuple[ResearchBacktestPriceObservation, ...]],
    ) -> ResearchBacktestAttribution:
        self._validate_inputs(backtest, target_portfolios, price_history_by_security)

        period_results: list[ResearchBacktestPeriodAttribution] = []
        total_gross = 0.0
        total_cost_drag = 0.0
        total_long = 0.0
        total_short = 0.0

        for period, portfolio in zip(backtest.periods, target_portfolios):
            contributions: list[ResearchBacktestPositionAttribution] = []
            long_contribution = 0.0
            short_contribution = 0.0

            capital_scale = period.starting_equity / backtest.initial_capital
            if not isfinite(capital_scale) or capital_scale <= 0.0:
                raise InvalidInputError("Backtest attribution capital scale must be finite and positive.")

            for position in portfolio.positions:
                prices = self._normalize_prices(
                    price_history_by_security.get(position.security_id, ())
                )
                start = self._first_after(prices, period.period_start)
                end = self._first_after(prices, period.period_end)
                if start is None or end is None:
                    raise InvalidInputError(
                        f"Missing historical price for security {position.security_id} "
                        f"across period {period.period_start.isoformat()} to "
                        f"{period.period_end.isoformat()}."
                    )

                start_price = self._select_price(start, backtest.price_basis)
                end_price = self._select_price(end, backtest.price_basis)
                if start_price <= 0.0 or end_price <= 0.0:
                    raise InvalidInputError("Backtest attribution prices must be strictly positive.")

                security_return = end_price / start_price - 1.0
                contribution = float(position.target_weight) * security_return
                if not isfinite(security_return) or not isfinite(contribution):
                    raise InvalidInputError("Backtest attribution values must be finite.")

                item = ResearchBacktestPositionAttribution(
                    period_start=period.period_start,
                    period_end=period.period_end,
                    symbol=position.symbol.strip().upper(),
                    security_id=position.security_id,
                    target_weight=float(position.target_weight),
                    security_return=security_return,
                    gross_contribution=contribution,
                    return_contribution=capital_scale * contribution,
                )
                contributions.append(item)

                if position.target_weight > 0.0:
                    long_contribution += contribution
                elif position.target_weight < 0.0:
                    short_contribution += contribution

            gross_return = sum(item.gross_contribution for item in contributions)
            if abs(gross_return - period.gross_return) > 1e-12:
                raise InvalidInputError(
                    "Backtest attribution does not reconcile to the recorded gross return."
                )

            cost_drag = period.net_return - period.gross_return
            if not isfinite(cost_drag):
                raise InvalidInputError("Backtest transaction-cost drag must be finite.")

            return_contribution = capital_scale * gross_return
            transaction_cost_return_contribution = capital_scale * cost_drag
            if not isfinite(return_contribution) or not isfinite(transaction_cost_return_contribution):
                raise InvalidInputError("Backtest return attribution must be finite.")
            net_return_contribution = capital_scale * period.net_return
            if abs(
                return_contribution
                + transaction_cost_return_contribution
                - net_return_contribution
            ) > 1e-12:
                raise InvalidInputError(
                    "Backtest period attribution does not reconcile to net return."
                )

            period_result = ResearchBacktestPeriodAttribution(
                period_start=period.period_start,
                period_end=period.period_end,
                starting_equity=period.starting_equity,
                ending_equity=period.ending_equity,
                gross_return=period.gross_return,
                transaction_cost_drag=cost_drag,
                net_return=period.net_return,
                long_contribution=capital_scale * long_contribution,
                short_contribution=capital_scale * short_contribution,
                return_contribution=return_contribution,
                transaction_cost_return_contribution=transaction_cost_return_contribution,
                position_contributions=tuple(contributions),
            )
            period_results.append(period_result)
            total_gross += return_contribution
            total_cost_drag += transaction_cost_return_contribution
            total_long += capital_scale * long_contribution
            total_short += capital_scale * short_contribution

        total_net = backtest.total_return
        total_cost_contribution = total_cost_drag
        if abs(total_gross - (total_long + total_short)) > 1e-12:
            raise InvalidInputError(
                "Backtest attribution does not reconcile gross contributions."
            )
        if abs(total_long + total_short + total_cost_contribution - total_net) > 1e-12:
            raise InvalidInputError("Backtest attribution does not reconcile to total return.")
        return ResearchBacktestAttribution(
            backtest_identity=(
                backtest.backtest_key,
                backtest.backtest_definition_version,
            ),
            periods=tuple(period_results),
            total_gross_return=total_gross,
            total_transaction_cost_drag=total_cost_drag,
            total_net_return=total_net,
            total_long_contribution=total_long,
            total_short_contribution=total_short,
            total_transaction_cost_return_contribution=total_cost_contribution,
        )

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
    def _select_price(observation, price_basis) -> float:
        value = observation.close if price_basis.value == "UNADJUSTED" else observation.adjusted_close
        if value is None:
            raise InvalidInputError(
                "Adjusted-price attribution requires adjusted_close for every valuation observation."
            )
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError("Backtest attribution prices must be numeric.") from exc
        if not isfinite(numeric):
            raise InvalidInputError("Backtest attribution prices must be finite.")
        return numeric

    @staticmethod
    def _normalize_prices(observations) -> tuple[ResearchBacktestPriceObservation, ...]:
        try:
            values = tuple(observations)
        except TypeError as exc:
            raise InvalidInputError("Backtest attribution price history must be iterable.") from exc
        seen = set()
        for observation in values:
            date = getattr(observation, "date", None)
            if not isinstance(date, datetime) or date.tzinfo is None:
                raise InvalidInputError("Backtest attribution price dates must be timezone-aware.")
            if date in seen:
                raise InvalidInputError("Backtest attribution price history contains duplicate dates.")
            seen.add(date)
        return tuple(sorted(values, key=lambda item: item.date))

    @staticmethod
    def _validate_inputs(backtest, target_portfolios, price_history_by_security) -> None:
        if not isinstance(backtest, ResearchBacktest):
            raise InvalidInputError("Attribution requires a ResearchBacktest.")
        if backtest.status.value != "COMPLETED":
            raise InvalidInputError("Attribution requires a completed backtest.")
        if not isinstance(target_portfolios, tuple):
            raise InvalidInputError("Attribution target portfolios must be supplied as a tuple.")
        if len(target_portfolios) != len(backtest.periods):
            raise InvalidInputError(
                "Attribution requires one target portfolio for each completed backtest period."
            )
        if not isinstance(price_history_by_security, Mapping):
            raise InvalidInputError("Attribution price history must be keyed by security ID.")

        for portfolio, period in zip(target_portfolios, backtest.periods):
            if not isinstance(portfolio, ResearchPortfolio):
                raise InvalidInputError("Attribution targets must use ResearchPortfolio.")
            if portfolio.status is not ResearchPortfolioConstructionStatus.CONSTRUCTED:
                raise InvalidInputError(
                    "Attribution targets must be constructed portfolios."
                )
            if portfolio.as_of != period.period_start:
                raise InvalidInputError(
                    "Attribution target portfolio boundaries must match backtest period starts."
                )
            if (
                portfolio.strategy_key,
                portfolio.strategy_definition_version,
            ) != backtest.strategy_identity:
                raise InvalidInputError("Attribution strategy identity does not match the backtest.")
