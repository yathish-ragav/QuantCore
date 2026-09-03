from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolioConstructionService,
)
from quantcore.services.research_rebalance_service import (
    ResearchRebalanceActionType,
    ResearchRebalanceDefinition,
    ResearchRebalanceFrequency,
    ResearchRebalanceService,
    ResearchRebalanceStatus,
)
from quantcore.services.research_signal_service import ResearchSignalPanel, ResearchSignalRow
from quantcore.services.research_strategy_service import ResearchStrategyDefinition, ResearchStrategyDirection


T0 = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)
T1 = datetime(2026, 1, 5, 15, 30, tzinfo=timezone.utc)


def strategy():
    return ResearchStrategyDefinition(
        strategy_key="quality",
        definition_version="1",
        signal_identity=("quality_signal", "1"),
        direction=ResearchStrategyDirection.LONG_ONLY,
        long_threshold=0.5,
        short_threshold=None,
    )


def panel(*rows):
    return ResearchSignalPanel(
        signal_key="quality_signal",
        definition_version="1",
        factor_identities=(),
        rows=tuple(rows),
        construction="TEST",
    )


def row(security_id, score, as_of=T1):
    return ResearchSignalRow(
        symbol=f"T{security_id}",
        security_id=security_id,
        as_of=as_of,
        score=score,
        centered_score=2 * score - 1,
        contributions=(),
    )


def portfolio_at(as_of, *rows):
    return ResearchPortfolioConstructionService().construct(strategy(), panel(*rows), as_of)


def definition():
    return ResearchRebalanceDefinition("weekly_quality", "1", ResearchRebalanceFrequency.WEEKLY)


def test_rebalance_classifies_add_increase_reduce_remove_and_reverse():
    # Use explicit weights so each transition class is independently observable.
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioPosition, ResearchPortfolioPositionSide, ResearchPortfolioConstructionStatus
    current = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T0, ResearchPortfolioConstructionStatus.CONSTRUCTED, (
        ResearchPortfolioPosition("T1", 1, T0, .9, ResearchPortfolioPositionSide.LONG, .10),
        ResearchPortfolioPosition("T2", 2, T0, .8, ResearchPortfolioPositionSide.LONG, .20),
        ResearchPortfolioPosition("T3", 3, T0, .7, ResearchPortfolioPositionSide.LONG, .10),
        ResearchPortfolioPosition("T4", 4, T0, .6, ResearchPortfolioPositionSide.LONG, .10),
    ), 4, 4, 0, .5, .5, "TEST")
    target = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T1, ResearchPortfolioConstructionStatus.CONSTRUCTED, (
        ResearchPortfolioPosition("T1", 1, T1, .9, ResearchPortfolioPositionSide.LONG, .05),
        ResearchPortfolioPosition("T2", 2, T1, .8, ResearchPortfolioPositionSide.LONG, .30),
        ResearchPortfolioPosition("T3", 3, T1, .7, ResearchPortfolioPositionSide.LONG, .00),
        ResearchPortfolioPosition("T5", 5, T1, .6, ResearchPortfolioPositionSide.LONG, -.10),
    ), 4, 3, 0, .45, .25, "TEST")
    result = ResearchRebalanceService().rebalance(current, target, definition(), T1)
    assert [(a.security_id, a.action) for a in result.actions] == [
        (1, ResearchRebalanceActionType.REDUCE),
        (2, ResearchRebalanceActionType.INCREASE),
        (3, ResearchRebalanceActionType.REMOVE),
        (4, ResearchRebalanceActionType.REMOVE),
        (5, ResearchRebalanceActionType.ADD),
    ]


def test_reverse_is_explicit():
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioPosition, ResearchPortfolioPositionSide, ResearchPortfolioConstructionStatus
    current = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T0, ResearchPortfolioConstructionStatus.CONSTRUCTED, (
        ResearchPortfolioPosition("T1", 1, T0, .9, ResearchPortfolioPositionSide.LONG, .10),), 1, 1, 0, .10, .10, "TEST")
    target = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T1, ResearchPortfolioConstructionStatus.CONSTRUCTED, (
        ResearchPortfolioPosition("T1", 1, T1, .1, ResearchPortfolioPositionSide.SHORT, -.10),), 1, 0, 1, .10, -.10, "TEST")
    result = ResearchRebalanceService().rebalance(current, target, definition(), T1)
    assert result.actions[0].action is ResearchRebalanceActionType.REVERSE
    assert result.actions[0].weight_delta == pytest.approx(-.20)


def test_zero_delta_is_omitted_and_status_is_no_changes():
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioPosition, ResearchPortfolioPositionSide, ResearchPortfolioConstructionStatus
    position0 = ResearchPortfolioPosition("T1", 1, T0, .9, ResearchPortfolioPositionSide.LONG, .10)
    position1 = ResearchPortfolioPosition("T1", 1, T1, .9, ResearchPortfolioPositionSide.LONG, .10)
    current = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T0, ResearchPortfolioConstructionStatus.CONSTRUCTED, (position0,), 1, 1, 0, .10, .10, "TEST")
    target = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T1, ResearchPortfolioConstructionStatus.CONSTRUCTED, (position1,), 1, 1, 0, .10, .10, "TEST")
    result = ResearchRebalanceService().rebalance(current, target, definition(), T1)
    assert result.actions == ()
    assert result.status is ResearchRebalanceStatus.NO_CHANGES
    assert result.turnover == 0


def test_turnover_is_half_absolute_weight_delta():
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioPosition, ResearchPortfolioPositionSide, ResearchPortfolioConstructionStatus
    current = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T0, ResearchPortfolioConstructionStatus.CONSTRUCTED, (
        ResearchPortfolioPosition("T1", 1, T0, .9, ResearchPortfolioPositionSide.LONG, .20),), 1, 1, 0, .20, .20, "TEST")
    target = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T1, ResearchPortfolioConstructionStatus.CONSTRUCTED, (
        ResearchPortfolioPosition("T1", 1, T1, .9, ResearchPortfolioPositionSide.LONG, .10),
        ResearchPortfolioPosition("T2", 2, T1, .8, ResearchPortfolioPositionSide.LONG, .20),), 2, 2, 0, .30, .30, "TEST")
    result = ResearchRebalanceService().rebalance(current, target, definition(), T1)
    assert result.turnover == pytest.approx(.15)


@pytest.mark.parametrize("field,value", [
    ("rebalance_key", ""),
    ("definition_version", ""),
])
def test_definition_rejects_empty_identity(field, value):
    values = {"rebalance_key": "r", "definition_version": "1", "frequency": ResearchRebalanceFrequency.WEEKLY}
    values[field] = value
    with pytest.raises(InvalidInputError):
        ResearchRebalanceDefinition(**values)


def test_definition_rejects_invalid_frequency():
    with pytest.raises(InvalidInputError):
        ResearchRebalanceDefinition("r", "1", "WEEKLY")


def test_current_portfolio_must_precede_rebalance_as_of():
    current = portfolio_at(T1, row(1, .9, T1))
    target = portfolio_at(T1, row(1, .9))
    with pytest.raises(InvalidInputError, match="must precede"):
        ResearchRebalanceService().rebalance(current, target, definition(), T1)


def test_target_portfolio_must_match_rebalance_as_of():
    current = portfolio_at(T0, row(1, .9, T0))
    target = portfolio_at(T0, row(1, .9, T0))
    with pytest.raises(InvalidInputError, match="Target portfolio as_of"):
        ResearchRebalanceService().rebalance(current, target, definition(), T1)


def test_target_must_be_constructed():
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioConstructionStatus
    target = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T1, ResearchPortfolioConstructionStatus.NO_ELIGIBLE_SECURITIES, (), 0, 0, 0, 0.0, 0.0, "NO_TARGET_POSITIONS")
    current = portfolio_at(T0, row(1, .9, T0))
    with pytest.raises(InvalidInputError, match="constructed"):
        ResearchRebalanceService().rebalance(current, target, definition(), T1)


def test_strategy_identity_must_match():
    current = portfolio_at(T0, row(1, .9, T0))
    other = ResearchStrategyDefinition("other", "1", ("quality_signal", "1"), ResearchStrategyDirection.LONG_ONLY, .5, None)
    target = ResearchPortfolioConstructionService().construct(other, panel(row(1, .9)), T1)
    with pytest.raises(InvalidInputError, match="strategy identity"):
        ResearchRebalanceService().rebalance(current, target, definition(), T1)


def test_signal_identity_must_match():
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioConstructionStatus
    current = portfolio_at(T0, row(1, .9, T0))
    target = ResearchPortfolio("quality", "1", ("other_signal", "1"), T1, ResearchPortfolioConstructionStatus.CONSTRUCTED, (), 0, 0, 0, 0.0, 0.0, "TEST")
    with pytest.raises(InvalidInputError, match="signal identity"):
        ResearchRebalanceService().rebalance(current, target, definition(), T1)


def test_as_of_must_be_timezone_aware():
    current = portfolio_at(T0, row(1, .9, T0))
    target = portfolio_at(T1, row(1, .9))
    with pytest.raises(InvalidInputError, match="timezone-aware"):
        ResearchRebalanceService().rebalance(current, target, definition(), T1.replace(tzinfo=None))


def test_actions_are_sorted_by_security_id():
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioPosition, ResearchPortfolioPositionSide, ResearchPortfolioConstructionStatus
    current = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T0, ResearchPortfolioConstructionStatus.CONSTRUCTED, (), 0, 0, 0, 0.0, 0.0, "TEST")
    target = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T1, ResearchPortfolioConstructionStatus.CONSTRUCTED, (
        ResearchPortfolioPosition("T3", 3, T1, .9, ResearchPortfolioPositionSide.LONG, .1),
        ResearchPortfolioPosition("T1", 1, T1, .8, ResearchPortfolioPositionSide.LONG, .1),), 2, 2, 0, .2, .2, "TEST")
    result = ResearchRebalanceService().rebalance(current, target, definition(), T1)
    assert [a.security_id for a in result.actions] == [1, 3]


def test_duplicate_current_security_ids_are_rejected():
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioPosition, ResearchPortfolioPositionSide, ResearchPortfolioConstructionStatus
    p1 = ResearchPortfolioPosition("T1", 1, T0, .9, ResearchPortfolioPositionSide.LONG, .1)
    p2 = ResearchPortfolioPosition("T1", 1, T0, .8, ResearchPortfolioPositionSide.LONG, .2)
    current = ResearchPortfolio("quality", "1", ("quality_signal", "1"), T0, ResearchPortfolioConstructionStatus.CONSTRUCTED, (p1, p2), 2, 2, 0, .3, .3, "TEST")
    target = portfolio_at(T1, row(1, .9))
    with pytest.raises(InvalidInputError, match="duplicate security"):
        ResearchRebalanceService().rebalance(current, target, definition(), T1)


def test_current_and_target_portfolios_require_same_strategy_version():
    from quantcore.services.research_portfolio_construction_service import ResearchPortfolio, ResearchPortfolioConstructionStatus
    current = portfolio_at(T0, row(1, .9, T0))
    target = ResearchPortfolio("quality", "2", ("quality_signal", "1"), T1, ResearchPortfolioConstructionStatus.CONSTRUCTED, (), 0, 0, 0, 0.0, 0.0, "TEST")
    with pytest.raises(InvalidInputError, match="strategy identity"):
        ResearchRebalanceService().rebalance(current, target, definition(), T1)
