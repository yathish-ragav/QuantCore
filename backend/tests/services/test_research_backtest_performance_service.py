from datetime import datetime, timedelta, timezone

import pytest

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_performance_service import (
    ResearchBacktestPerformanceService,
)
from quantcore.services.research_backtest_service import (
    ResearchBacktest,
    ResearchBacktestDefinition,
    ResearchBacktestPeriod,
    ResearchBacktestPeriodStatus,
    ResearchBacktestStatus,
)
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolioConstructionService,
)
from quantcore.services.research_rebalance_service import (
    ResearchRebalanceDefinition,
    ResearchRebalanceFrequency,
)
from quantcore.services.research_signal_service import ResearchSignalPanel, ResearchSignalRow
from quantcore.services.research_strategy_service import (
    ResearchStrategyDefinition,
    ResearchStrategyDirection,
)
from quantcore.services.research_transaction_cost_service import (
    ResearchTransactionCostDefinition,
)


AS_OF_0 = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)
AS_OF_1 = datetime(2026, 1, 5, 15, 30, tzinfo=timezone.utc)
AS_OF_2 = datetime(2026, 1, 8, 15, 30, tzinfo=timezone.utc)


class Price:
    def __init__(self, date, close, adjusted_close=None):
        self.date = date
        self.close = close
        self.adjusted_close = adjusted_close if adjusted_close is not None else close


def strategy():
    return ResearchStrategyDefinition(
        strategy_key="quality",
        definition_version="1",
        signal_identity=("quality_signal", "1"),
        direction=ResearchStrategyDirection.LONG_ONLY,
        long_threshold=0.8,
    )


def panel(*rows):
    return ResearchSignalPanel(
        signal_key="quality_signal",
        definition_version="1",
        factor_identities=(),
        rows=tuple(rows),
        construction="TEST",
    )


def row(security_id, score, as_of):
    return ResearchSignalRow(
        symbol=f"S{security_id}",
        security_id=security_id,
        as_of=as_of,
        score=score,
        centered_score=2 * score - 1,
        contributions=(),
    )


def target(as_of, *rows):
    return ResearchPortfolioConstructionService().construct(
        strategy(), panel(*rows), as_of
    )


def definition():
    return ResearchBacktestDefinition(
        backtest_key="quality_backtest",
        definition_version="1",
        strategy_identity=("quality", "1"),
        constraint_identity=("basic", "1"),
        rebalance_identity=("daily", "1"),
        transaction_cost_identity=("tc", "1"),
        start_as_of=AS_OF_0,
        end_as_of=AS_OF_2,
        initial_capital=1_000_000,
        price_basis=PriceBasis.UNADJUSTED,
    )


def constraint():
    return ResearchPortfolioConstraintDefinition(
        constraint_key="basic",
        definition_version="1",
        max_position_weight=1.0,
        max_gross_exposure=1.0,
    )


def rebalance_definition():
    return ResearchRebalanceDefinition(
        rebalance_key="daily",
        definition_version="1",
        frequency=ResearchRebalanceFrequency.DAILY,
    )


def transaction_cost_definition():
    return ResearchTransactionCostDefinition(
        cost_key="tc",
        definition_version="1",
        one_way_cost_bps=10.0,
    )


def prices(*values):
    dates = (
        AS_OF_0 + timedelta(hours=1),
        AS_OF_1 + timedelta(hours=1),
        AS_OF_2 + timedelta(hours=1),
    )
    return [Price(date, close) for date, close in zip(dates, values)]


def backtest():
    from quantcore.services.research_backtest_service import ResearchBacktestService

    return ResearchBacktestService().run(
        definition(),
        [
            target(AS_OF_0, row(1, 0.9, AS_OF_0)),
            target(AS_OF_1, row(2, 0.95, AS_OF_1)),
            target(AS_OF_2, row(2, 0.95, AS_OF_2)),
        ],
        {
            1: prices(100, 110, 120),
            2: prices(50, 50, 55),
        },
        constraint(),
        rebalance_definition(),
        transaction_cost_definition(),
    )


def test_analyze_returns_identity_and_core_metrics():
    result = ResearchBacktestPerformanceService().analyze(backtest())

    assert result.backtest_identity == ("quality_backtest", "1")
    assert result.period_count == 2
    assert result.initial_capital == pytest.approx(1_000_000.0)
    assert result.final_equity == pytest.approx(1_208_790.0)
    assert result.total_return == pytest.approx(0.20879)
    assert result.winning_periods == 2
    assert result.losing_periods == 0
    assert result.flat_periods == 0
    assert result.win_rate == pytest.approx(1.0)


def test_max_drawdown_is_zero_for_monotonically_rising_equity():
    result = ResearchBacktestPerformanceService().analyze(backtest())

    assert result.maximum_drawdown == pytest.approx(0.0)
    assert result.maximum_drawdown_duration_days == pytest.approx(0.0)


def test_metrics_are_finite_and_deterministic():
    service = ResearchBacktestPerformanceService()
    first = service.analyze(backtest())
    second = service.analyze(backtest())

    assert first == second
    for value in (
        first.total_return,
        first.annualized_return,
        first.annualized_volatility,
        first.maximum_drawdown,
        first.maximum_drawdown_duration_days,
        first.average_period_return,
        first.average_turnover,
    ):
        assert value == pytest.approx(value)
        assert value == value


def test_flat_periods_do_not_count_as_wins_or_losses():
    bt = backtest()
    flat = ResearchBacktestPeriod(
        period_start=AS_OF_0,
        period_end=AS_OF_1,
        starting_equity=1_000_000.0,
        ending_equity=1_000_000.0,
        gross_return=0.0,
        transaction_cost_fraction=0.0,
        net_return=0.0,
        turnover=0.0,
        status=ResearchBacktestPeriodStatus.COMPLETED,
    )
    modified = ResearchBacktest(
        backtest_key=bt.backtest_key,
        backtest_definition_version=bt.backtest_definition_version,
        strategy_identity=bt.strategy_identity,
        constraint_identity=bt.constraint_identity,
        rebalance_identity=bt.rebalance_identity,
        transaction_cost_identity=bt.transaction_cost_identity,
        start_as_of=bt.start_as_of,
        end_as_of=bt.end_as_of,
        initial_capital=1_000_000.0,
        final_equity=1_000_000.0,
        total_return=0.0,
        price_basis=bt.price_basis,
        periods=(flat,),
        status=ResearchBacktestStatus.COMPLETED,
    )
    result = ResearchBacktestPerformanceService().analyze(modified)

    assert result.winning_periods == 0
    assert result.losing_periods == 0
    assert result.flat_periods == 1
    assert result.win_rate == pytest.approx(0.0)


def test_non_backtest_input_is_rejected():
    with pytest.raises(InvalidInputError):
        ResearchBacktestPerformanceService().analyze(object())


def test_empty_periods_are_rejected():
    bt = backtest()
    empty = ResearchBacktest(
        backtest_key=bt.backtest_key,
        backtest_definition_version=bt.backtest_definition_version,
        strategy_identity=bt.strategy_identity,
        constraint_identity=bt.constraint_identity,
        rebalance_identity=bt.rebalance_identity,
        transaction_cost_identity=bt.transaction_cost_identity,
        start_as_of=bt.start_as_of,
        end_as_of=bt.end_as_of,
        initial_capital=bt.initial_capital,
        final_equity=bt.final_equity,
        total_return=bt.total_return,
        price_basis=bt.price_basis,
        periods=(),
        status=ResearchBacktestStatus.COMPLETED,
    )
    with pytest.raises(InvalidInputError, match="at least one"):
        ResearchBacktestPerformanceService().analyze(empty)


def test_incomplete_period_is_rejected():
    bt = backtest()
    period = bt.periods[0]
    incomplete = ResearchBacktestPeriod(
        period_start=period.period_start,
        period_end=period.period_end,
        starting_equity=period.starting_equity,
        ending_equity=period.ending_equity,
        gross_return=period.gross_return,
        transaction_cost_fraction=period.transaction_cost_fraction,
        net_return=period.net_return,
        turnover=period.turnover,
        status=ResearchBacktestPeriodStatus.COMPLETED,
    )
    # The current backtest contract only exposes COMPLETED periods, so use an
    # invalid period boundary to verify input validation without weakening the enum.
    invalid = ResearchBacktestPeriod(
        period_start=period.period_end,
        period_end=period.period_start,
        starting_equity=period.starting_equity,
        ending_equity=period.ending_equity,
        gross_return=period.gross_return,
        transaction_cost_fraction=period.transaction_cost_fraction,
        net_return=period.net_return,
        turnover=period.turnover,
        status=incomplete.status,
    )
    modified = ResearchBacktest(
        backtest_key=bt.backtest_key,
        backtest_definition_version=bt.backtest_definition_version,
        strategy_identity=bt.strategy_identity,
        constraint_identity=bt.constraint_identity,
        rebalance_identity=bt.rebalance_identity,
        transaction_cost_identity=bt.transaction_cost_identity,
        start_as_of=bt.start_as_of,
        end_as_of=bt.end_as_of,
        initial_capital=bt.initial_capital,
        final_equity=bt.final_equity,
        total_return=bt.total_return,
        price_basis=bt.price_basis,
        periods=(invalid,),
        status=ResearchBacktestStatus.COMPLETED,
    )
    with pytest.raises(InvalidInputError, match="positive duration"):
        ResearchBacktestPerformanceService().analyze(modified)
