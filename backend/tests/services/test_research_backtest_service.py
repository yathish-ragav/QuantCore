from datetime import datetime, timedelta, timezone

import pytest

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_service import (
    ResearchBacktestDefinition,
    ResearchBacktestPeriodStatus,
    ResearchBacktestService,
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
        strategy(),
        panel(*rows),
        as_of,
    )


def definition(price_basis=PriceBasis.UNADJUSTED):
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
        price_basis=price_basis,
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


def run_backtest(targets, price_history):
    return ResearchBacktestService().run(
        definition(),
        targets,
        price_history,
        constraint(),
        rebalance_definition(),
        transaction_cost_definition(),
    )


def test_definition_requires_positive_capital():
    with pytest.raises(InvalidInputError):
        ResearchBacktestDefinition(
            backtest_key="b",
            definition_version="1",
            strategy_identity=("s", "1"),
            constraint_identity=("c", "1"),
            rebalance_identity=("r", "1"),
            transaction_cost_identity=("tc", "1"),
            start_as_of=AS_OF_0,
            end_as_of=AS_OF_1,
            initial_capital=0,
        )


def test_definition_requires_ordered_interval():
    with pytest.raises(InvalidInputError):
        ResearchBacktestDefinition(
            backtest_key="b",
            definition_version="1",
            strategy_identity=("s", "1"),
            constraint_identity=("c", "1"),
            rebalance_identity=("r", "1"),
            transaction_cost_identity=("tc", "1"),
            start_as_of=AS_OF_1,
            end_as_of=AS_OF_0,
            initial_capital=100,
        )


def test_two_target_boundaries_produce_one_completed_period():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    result = run_backtest(targets, {1: prices(100, 110, 120)})

    assert result.status is ResearchBacktestStatus.COMPLETED
    assert len(result.periods) == 1
    assert result.periods[0].status is ResearchBacktestPeriodStatus.COMPLETED
    assert result.periods[0].gross_return == pytest.approx(0.20)
    assert result.periods[0].turnover == pytest.approx(0.0)
    assert result.final_equity == pytest.approx(1_200_000.0)


def test_transaction_cost_reduces_equity_at_rebalance():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_1, row(2, 0.95, AS_OF_1)),
        target(AS_OF_2, row(2, 0.95, AS_OF_2)),
    ]
    result = run_backtest(
        targets,
        {
            1: prices(100, 110, 120),
            2: prices(50, 50, 55),
        },
    )

    assert result.periods[0].gross_return == pytest.approx(0.10)
    assert result.periods[0].turnover == pytest.approx(1.0)
    assert result.periods[0].transaction_cost_fraction == pytest.approx(0.001)
    assert result.periods[0].net_return == pytest.approx(0.0989)
    assert result.periods[1].gross_return == pytest.approx(0.10)
    assert result.final_equity == pytest.approx(1_208_790.0)


def test_adjusted_price_basis_requires_adjusted_close():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    adjusted_definition = definition(PriceBasis.ADJUSTED)
    service = ResearchBacktestService()

    class MissingAdjusted:
        def __init__(self, date, close):
            self.date = date
            self.close = close
            self.adjusted_close = None

    with pytest.raises(InvalidInputError):
        service.run(
            adjusted_definition,
            targets,
            {1: [MissingAdjusted(p.date, p.close) for p in prices(100, 110, 120)]},
            constraint(),
            rebalance_definition(),
            transaction_cost_definition(),
        )


def test_missing_price_is_rejected():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    with pytest.raises(InvalidInputError, match="Missing historical price"):
        run_backtest(targets, {1: prices(100)})


def test_targets_must_be_ascending():
    targets = [
        target(AS_OF_1, row(1, 0.9, AS_OF_1)),
        target(AS_OF_0, row(1, 0.95, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    with pytest.raises(InvalidInputError, match="ascending"):
        run_backtest(targets, {1: prices(100, 110, 120)})


def test_targets_must_cover_definition_boundaries():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_1, row(1, 0.95, AS_OF_1)),
    ]
    with pytest.raises(InvalidInputError, match="boundaries"):
        run_backtest(targets, {1: prices(100, 110, 120)})


def test_target_strategy_identity_must_match_definition():
    other_strategy = ResearchStrategyDefinition(
        strategy_key="value",
        definition_version="1",
        signal_identity=("value_signal", "1"),
        direction=ResearchStrategyDirection.LONG_ONLY,
        long_threshold=0.8,
    )
    other_panel = ResearchSignalPanel(
        signal_key="value_signal",
        definition_version="1",
        factor_identities=(),
        rows=(row(1, 0.9, AS_OF_0),),
        construction="TEST",
    )
    first = ResearchPortfolioConstructionService().construct(other_strategy, other_panel, AS_OF_0)
    second = target(AS_OF_2, row(1, 0.9, AS_OF_2))
    with pytest.raises(InvalidInputError, match="strategy identity"):
        run_backtest([first, second], {1: prices(100, 110, 120)})


def test_constraint_identity_must_match_definition():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    bad_constraint = ResearchPortfolioConstraintDefinition(
        constraint_key="other",
        definition_version="1",
        max_position_weight=1.0,
    )
    with pytest.raises(InvalidInputError, match="constraint identity"):
        ResearchBacktestService().run(
            definition(),
            targets,
            {1: prices(100, 110, 120)},
            bad_constraint,
            rebalance_definition(),
            transaction_cost_definition(),
        )


def test_rebalance_identity_must_match_definition():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    bad = ResearchRebalanceDefinition(
        rebalance_key="weekly",
        definition_version="1",
        frequency=ResearchRebalanceFrequency.WEEKLY,
    )
    with pytest.raises(InvalidInputError, match="rebalance identity"):
        ResearchBacktestService().run(
            definition(),
            targets,
            {1: prices(100, 110, 120)},
            constraint(),
            bad,
            transaction_cost_definition(),
        )


def test_transaction_cost_identity_must_match_definition():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    bad = ResearchTransactionCostDefinition(
        cost_key="other",
        definition_version="1",
        one_way_cost_bps=10,
    )
    with pytest.raises(InvalidInputError, match="transaction-cost identity"):
        ResearchBacktestService().run(
            definition(),
            targets,
            {1: prices(100, 110, 120)},
            constraint(),
            rebalance_definition(),
            bad,
        )


def test_duplicate_target_as_of_is_rejected():
    first = target(AS_OF_0, row(1, 0.9, AS_OF_0))
    duplicate = target(AS_OF_0, row(1, 0.95, AS_OF_0))
    last = target(AS_OF_2, row(1, 0.95, AS_OF_2))
    with pytest.raises(InvalidInputError, match="duplicate as_of"):
        run_backtest([first, duplicate, last], {1: prices(100, 110, 120)})


def test_duplicate_price_dates_are_rejected():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    p = prices(100, 110, 120)
    p.append(p[-1])
    with pytest.raises(InvalidInputError, match="duplicate dates"):
        run_backtest(targets, {1: p})


def test_price_at_boundary_is_not_used_as_entry():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_2, row(1, 0.95, AS_OF_2)),
    ]
    boundary_price = Price(AS_OF_0, 1)
    later = Price(AS_OF_0 + timedelta(hours=1), 100)
    end = Price(AS_OF_2 + timedelta(hours=1), 120)
    result = run_backtest(targets, {1: [boundary_price, later, end]})
    assert result.periods[0].gross_return == pytest.approx(0.20)


def test_non_constructed_target_is_rejected():
    empty_strategy = ResearchStrategyDefinition(
        strategy_key="empty",
        definition_version="1",
        signal_identity=("empty_signal", "1"),
        direction=ResearchStrategyDirection.LONG_ONLY,
        long_threshold=0.99,
    )
    empty_panel = ResearchSignalPanel(
        signal_key="empty_signal",
        definition_version="1",
        factor_identities=(),
        rows=(row(1, 0.5, AS_OF_0),),
        construction="TEST",
    )
    empty = ResearchPortfolioConstructionService().construct(
        empty_strategy, empty_panel, AS_OF_0
    )
    empty_later = ResearchPortfolioConstructionService().construct(
        empty_strategy,
        ResearchSignalPanel(
            signal_key="empty_signal",
            definition_version="1",
            factor_identities=(),
            rows=(row(1, 0.5, AS_OF_2),),
            construction="TEST",
        ),
        AS_OF_2,
    )
    backtest_definition = ResearchBacktestDefinition(
        backtest_key="empty_backtest",
        definition_version="1",
        strategy_identity=("empty", "1"),
        constraint_identity=("basic", "1"),
        rebalance_identity=("daily", "1"),
        transaction_cost_identity=("tc", "1"),
        start_as_of=AS_OF_0,
        end_as_of=AS_OF_2,
        initial_capital=1_000_000,
    )
    with pytest.raises(InvalidInputError, match="constructed target portfolios"):
        ResearchBacktestService().run(
            backtest_definition,
            [empty, empty_later],
            {1: prices(100, 110, 120)},
            constraint(),
            rebalance_definition(),
            transaction_cost_definition(),
        )


def test_backtest_is_deterministic():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0)),
        target(AS_OF_1, row(2, 0.95, AS_OF_1)),
        target(AS_OF_2, row(2, 0.95, AS_OF_2)),
    ]
    history = {
        1: prices(100, 110, 120),
        2: prices(50, 50, 55),
    }
    first = run_backtest(targets, history)
    second = run_backtest(targets, history)
    assert first == second


def test_empty_target_portfolio_is_rejected_by_constraint_layer():
    empty_strategy = ResearchStrategyDefinition(
        strategy_key="empty",
        definition_version="1",
        signal_identity=("empty_signal", "1"),
        direction=ResearchStrategyDirection.LONG_ONLY,
        long_threshold=0.99,
    )
    empty_panel = ResearchSignalPanel(
        signal_key="empty_signal",
        definition_version="1",
        factor_identities=(),
        rows=(row(1, 0.5, AS_OF_0),),
        construction="TEST",
    )
    empty = ResearchPortfolioConstructionService().construct(
        empty_strategy, empty_panel, AS_OF_0
    )
    with pytest.raises(InvalidInputError, match="strategy identity"):
        run_backtest(
            [empty, target(AS_OF_2, row(1, 0.95, AS_OF_2))],
            {1: prices(100, 110, 120)},
        )
