from dataclasses import dataclass
from math import isfinite, log, sqrt

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_service import ResearchBacktest


@dataclass(frozen=True)
class ResearchBacktestPerformance:
    """Deterministic performance and realized-risk summary for one backtest."""

    backtest_identity: tuple[str, str]
    period_count: int
    initial_capital: float
    final_equity: float
    total_return: float
    annualized_return: float
    annualized_volatility: float
    maximum_drawdown: float
    maximum_drawdown_duration_days: float
    average_period_return: float
    winning_periods: int
    losing_periods: int
    flat_periods: int
    average_turnover: float

    @property
    def win_rate(self) -> float:
        """Return the fraction of non-flat periods with a positive return."""
        directional_periods = self.winning_periods + self.losing_periods
        if directional_periods == 0:
            return 0.0
        return self.winning_periods / directional_periods


class ResearchBacktestPerformanceService:
    """Compute deterministic performance metrics from a completed backtest.

    Metrics are derived only from the immutable backtest result. No market-data
    access, forecasting, strategy mutation, or execution logic occurs here.

    Volatility is an annualized realized log-return rate volatility. Periods may
    have different calendar lengths; each period's log return is converted to a
    per-year rate and weighted by its elapsed calendar duration.
    """

    def analyze(self, backtest: ResearchBacktest) -> ResearchBacktestPerformance:
        if not isinstance(backtest, ResearchBacktest):
            raise InvalidInputError("Performance analysis requires a ResearchBacktest.")
        if not backtest.periods:
            raise InvalidInputError(
                "Performance analysis requires at least one completed backtest period."
            )

        for period in backtest.periods:
            if period.status.value != "COMPLETED":
                raise InvalidInputError(
                    "Performance analysis requires completed backtest periods."
                )
            if period.period_end <= period.period_start:
                raise InvalidInputError("Backtest periods must have positive duration.")
            if not isfinite(period.starting_equity) or period.starting_equity <= 0.0:
                raise InvalidInputError("Backtest starting equity must be finite and positive.")
            if not isfinite(period.ending_equity) or period.ending_equity <= 0.0:
                raise InvalidInputError("Backtest ending equity must be finite and positive.")
            if not isfinite(period.net_return) or period.net_return <= -1.0:
                raise InvalidInputError("Backtest net returns must be finite and greater than -100%.")
            if not isfinite(period.turnover) or period.turnover < 0.0:
                raise InvalidInputError("Backtest turnover must be finite and non-negative.")

        total_return = backtest.final_equity / backtest.initial_capital - 1.0
        elapsed_years = (
            backtest.end_as_of - backtest.start_as_of
        ).total_seconds() / (365.25 * 24.0 * 60.0 * 60.0)
        if elapsed_years <= 0.0:
            raise InvalidInputError("Backtest interval must have positive elapsed time.")

        annualized_return = (1.0 + total_return) ** (1.0 / elapsed_years) - 1.0

        weighted_rate_sum = 0.0
        total_years = 0.0
        rates: list[tuple[float, float]] = []
        for period in backtest.periods:
            years = (
                period.period_end - period.period_start
            ).total_seconds() / (365.25 * 24.0 * 60.0 * 60.0)
            log_return = log(1.0 + period.net_return)
            rate = log_return / years
            rates.append((rate, years))
            weighted_rate_sum += rate * years
            total_years += years

        mean_rate = weighted_rate_sum / total_years
        variance = sum(
            years * (rate - mean_rate) ** 2
            for rate, years in rates
        ) / total_years
        annualized_volatility = sqrt(max(variance, 0.0))

        peak = backtest.initial_capital
        maximum_drawdown = 0.0
        peak_date = backtest.start_as_of
        max_drawdown_duration_days = 0.0

        for period in backtest.periods:
            equity = period.ending_equity
            if equity > peak:
                peak = equity
                peak_date = period.period_end
            drawdown = equity / peak - 1.0
            if drawdown < maximum_drawdown:
                maximum_drawdown = drawdown
                max_drawdown_duration_days = (
                    period.period_end - peak_date
                ).total_seconds() / (24.0 * 60.0 * 60.0)

        returns = tuple(period.net_return for period in backtest.periods)
        winning = sum(value > 0.0 for value in returns)
        losing = sum(value < 0.0 for value in returns)
        flat = len(returns) - winning - losing
        average_return = sum(returns) / len(returns)
        average_turnover = (
            sum(period.turnover for period in backtest.periods) / len(backtest.periods)
        )

        return ResearchBacktestPerformance(
            backtest_identity=(
                backtest.backtest_key,
                backtest.backtest_definition_version,
            ),
            period_count=len(backtest.periods),
            initial_capital=backtest.initial_capital,
            final_equity=backtest.final_equity,
            total_return=total_return,
            annualized_return=annualized_return,
            annualized_volatility=annualized_volatility,
            maximum_drawdown=maximum_drawdown,
            maximum_drawdown_duration_days=max_drawdown_duration_days,
            average_period_return=average_return,
            winning_periods=winning,
            losing_periods=losing,
            flat_periods=flat,
            average_turnover=average_turnover,
        )
