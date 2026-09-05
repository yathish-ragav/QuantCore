from datetime import datetime, timedelta, timezone

import pytest

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_attribution_service import (
    ResearchBacktestAttributionService,
)
from quantcore.services.research_backtest_service import (
    ResearchBacktestDefinition,
    ResearchBacktestService,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolioConstructionService,
)
from quantcore.services.research_backtest_service import ResearchBacktestPriceObservation
from quantcore.services.research_portfolio_constraint_service import ResearchPortfolioConstraintDefinition
from quantcore.services.research_rebalance_service import ResearchRebalanceDefinition, ResearchRebalanceFrequency
from quantcore.services.research_signal_service import ResearchSignalPanel, ResearchSignalRow
from quantcore.services.research_strategy_service import ResearchStrategyDefinition, ResearchStrategyDirection
from quantcore.services.research_transaction_cost_service import ResearchTransactionCostDefinition


AS_OF_0 = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)
AS_OF_1 = datetime(2026, 1, 5, 15, 30, tzinfo=timezone.utc)
AS_OF_2 = datetime(2026, 1, 8, 15, 30, tzinfo=timezone.utc)


class Price:
    def __init__(self, date, close, adjusted_close=None):
        self.date = date
        self.close = close
        self.adjusted_close = adjusted_close if adjusted_close is not None else close


def strategy(direction=ResearchStrategyDirection.LONG_SHORT):
    return ResearchStrategyDefinition(
        strategy_key="quality", definition_version="1",
        signal_identity=("quality_signal", "1"), direction=direction,
        long_threshold=0.8 if direction is not ResearchStrategyDirection.SHORT_ONLY else None,
        short_threshold=0.2 if direction is not ResearchStrategyDirection.LONG_ONLY else None,
    )


def panel(*rows):
    return ResearchSignalPanel("quality_signal", "1", (), tuple(rows), "TEST")


def row(security_id, score, as_of):
    return ResearchSignalRow(f"S{security_id}", security_id, as_of, score, 2 * score - 1, ())


def target(as_of, *rows, direction=ResearchStrategyDirection.LONG_SHORT):
    return ResearchPortfolioConstructionService().construct(
        strategy(direction), panel(*rows), as_of
    )


def definition():
    return ResearchBacktestDefinition(
        "quality_backtest", "1", ("quality", "1"), ("basic", "1"),
        ("daily", "1"), ("tc", "1"), AS_OF_0, AS_OF_2, 1_000_000,
        PriceBasis.UNADJUSTED,
    )


def constraint():
    return ResearchPortfolioConstraintDefinition("basic", "1", max_position_weight=1.0, max_gross_exposure=2.0)


def rebalance():
    return ResearchRebalanceDefinition("daily", "1", ResearchRebalanceFrequency.DAILY)


def costs():
    return ResearchTransactionCostDefinition("tc", "1", 10.0)


def prices(*values):
    dates = (AS_OF_0 + timedelta(hours=1), AS_OF_1 + timedelta(hours=1), AS_OF_2 + timedelta(hours=1))
    return [Price(date, value) for date, value in zip(dates, values)]


def run(targets, history):
    return ResearchBacktestService().run(definition(), targets, history, constraint(), rebalance(), costs())


def test_attribution_reconciles_position_contributions_to_gross_return():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0), row(2, 0.1, AS_OF_0)),
        target(AS_OF_1, row(1, 0.9, AS_OF_1), row(2, 0.1, AS_OF_1)),
        target(AS_OF_2, row(1, 0.9, AS_OF_2), row(2, 0.1, AS_OF_2)),
    ]
    history = {1: prices(100, 110, 120), 2: prices(100, 90, 80)}
    bt = run(targets, history)

    result = ResearchBacktestAttributionService().attribute(
        bt, tuple(targets[:-1]), {1: tuple(history[1]), 2: tuple(history[2])}
    )

    assert len(result.periods) == 2
    assert result.periods[0].long_contribution == pytest.approx(0.10)
    assert result.periods[0].short_contribution == pytest.approx(0.10)
    assert result.periods[0].return_contribution == pytest.approx(
        result.periods[0].gross_return
    )
    assert sum(x.gross_contribution for x in result.periods[0].position_contributions) == pytest.approx(
        result.periods[0].gross_return
    )
    assert result.periods[0].transaction_cost_drag == pytest.approx(0.0)
    assert result.total_gross_return == pytest.approx(0.4424242424242424)
    assert result.total_transaction_cost_drag == pytest.approx(0.0)
    assert result.total_net_return == pytest.approx(bt.total_return)
    assert (
        result.total_long_contribution
        + result.total_short_contribution
        + result.total_transaction_cost_return_contribution
        == pytest.approx(bt.total_return)
    )


def test_long_short_contribution_preserves_direction():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0), row(2, 0.1, AS_OF_0)),
        target(AS_OF_2, row(1, 0.9, AS_OF_2), row(2, 0.1, AS_OF_2)),
    ]
    history = {1: prices(100, 120, 120), 2: prices(100, 90, 90)}
    bt = run(targets, history)
    result = ResearchBacktestAttributionService().attribute(
        bt, tuple(targets[:-1]), {1: tuple(history[1]), 2: tuple(history[2])}
    )
    period = result.periods[0]
    assert period.long_contribution == pytest.approx(0.2)
    assert period.short_contribution == pytest.approx(0.1)
    assert period.return_contribution == pytest.approx(0.3)


def test_requires_one_target_per_period():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0), direction=ResearchStrategyDirection.LONG_ONLY),
        target(AS_OF_2, row(1, 0.9, AS_OF_2), direction=ResearchStrategyDirection.LONG_ONLY),
    ]
    bt = run(targets, {1: prices(100, 110, 120)})
    with pytest.raises(InvalidInputError, match="one target portfolio"):
        ResearchBacktestAttributionService().attribute(bt, tuple(targets), {1: tuple(prices(100,110,120))})


def test_boundary_mismatch_is_rejected():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0), direction=ResearchStrategyDirection.LONG_ONLY),
        target(AS_OF_2, row(1, 0.9, AS_OF_2), direction=ResearchStrategyDirection.LONG_ONLY),
    ]
    bt = run(targets, {1: prices(100, 110, 120)})
    wrong = target(AS_OF_1, row(1, 0.9, AS_OF_1), direction=ResearchStrategyDirection.LONG_ONLY)
    with pytest.raises(InvalidInputError, match="boundaries"):
        ResearchBacktestAttributionService().attribute(bt, (wrong,), {1: tuple(prices(100,110,120))})


def test_missing_price_is_rejected():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0), direction=ResearchStrategyDirection.LONG_ONLY),
        target(AS_OF_2, row(1, 0.9, AS_OF_2), direction=ResearchStrategyDirection.LONG_ONLY),
    ]
    bt = run(targets, {1: prices(100, 110, 120)})
    with pytest.raises(InvalidInputError, match="Missing historical price"):
        ResearchBacktestAttributionService().attribute(bt, tuple(targets[:-1]), {1: tuple(prices(100,))})


def test_transaction_cost_drag_is_capital_scaled_and_reconciles():
    targets = [
        target(
            AS_OF_0,
            row(1, 0.9, AS_OF_0),
            row(2, 0.1, AS_OF_0),
        ),
        target(
            AS_OF_1,
            row(1, 0.1, AS_OF_1),
            row(2, 0.9, AS_OF_1),
        ),
        target(
            AS_OF_2,
            row(1, 0.1, AS_OF_2),
            row(2, 0.9, AS_OF_2),
        ),
    ]
    history = {1: prices(100, 110, 120), 2: prices(100, 90, 80)}
    bt = run(targets, history)
    result = ResearchBacktestAttributionService().attribute(
        bt, tuple(targets[:-1]), {1: tuple(history[1]), 2: tuple(history[2])}
    )

    period = result.periods[0]
    assert period.gross_return == pytest.approx(0.20)
    assert period.transaction_cost_drag == pytest.approx(-0.0024)
    assert period.transaction_cost_return_contribution == pytest.approx(-0.0024)
    assert (
        period.return_contribution + period.transaction_cost_return_contribution
        == pytest.approx(period.net_return)
    )
    assert result.total_transaction_cost_drag == pytest.approx(-0.0024)
    assert result.total_gross_return == pytest.approx(result.total_long_contribution + result.total_short_contribution)


def test_non_backtest_is_rejected():
    with pytest.raises(InvalidInputError):
        ResearchBacktestAttributionService().attribute(object(), (), {})


def test_deterministic_identity():
    targets = [
        target(AS_OF_0, row(1, 0.9, AS_OF_0), direction=ResearchStrategyDirection.LONG_ONLY),
        target(AS_OF_2, row(1, 0.9, AS_OF_2), direction=ResearchStrategyDirection.LONG_ONLY),
    ]
    history = {1: prices(100, 110, 120)}
    bt = run(targets, history)
    service = ResearchBacktestAttributionService()
    args = (bt, tuple(targets[:-1]), {1: tuple(history[1])})
    assert service.attribute(*args) == service.attribute(*args)
