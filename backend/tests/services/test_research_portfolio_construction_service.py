from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolioConstructionService,
    ResearchPortfolioConstructionStatus,
    ResearchPortfolioPositionSide,
)
from quantcore.services.research_signal_service import (
    ResearchSignalPanel,
    ResearchSignalRow,
)
from quantcore.services.research_strategy_service import (
    ResearchStrategyDefinition,
    ResearchStrategyDirection,
)


AS_OF = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


def strategy(direction=ResearchStrategyDirection.LONG_ONLY, **overrides):
    values = {
        "strategy_key": "quality",
        "definition_version": "1",
        "signal_identity": ("quality_signal", "1"),
        "direction": direction,
        "long_threshold": 0.8 if direction is not ResearchStrategyDirection.SHORT_ONLY else None,
        "short_threshold": 0.2 if direction is ResearchStrategyDirection.SHORT_ONLY else None,
    }
    if direction is ResearchStrategyDirection.LONG_SHORT:
        values.update(long_threshold=0.8, short_threshold=0.2)
    values.update(overrides)
    return ResearchStrategyDefinition(**values)


def row(security_id, score, as_of=AS_OF, symbol=None):
    return ResearchSignalRow(
        symbol=symbol or f"T{security_id}",
        security_id=security_id,
        as_of=as_of,
        score=score,
        centered_score=2 * score - 1,
        contributions=(),
    )


def panel(*rows, identity=("quality_signal", "1")):
    return ResearchSignalPanel(
        signal_key=identity[0],
        definition_version=identity[1],
        factor_identities=(),
        rows=tuple(rows),
        construction="TEST",
    )


def test_long_only_equal_weights_selected_by_threshold():
    result = ResearchPortfolioConstructionService().construct(
        strategy(), panel(row(3, 0.9), row(1, 0.8), row(2, 0.7)), AS_OF
    )

    assert result.status is ResearchPortfolioConstructionStatus.CONSTRUCTED
    assert [(p.security_id, p.target_weight, p.side) for p in result.positions] == [
        (1, 0.5, ResearchPortfolioPositionSide.LONG),
        (3, 0.5, ResearchPortfolioPositionSide.LONG),
    ]
    assert result.gross_exposure == pytest.approx(1.0)
    assert result.net_exposure == pytest.approx(1.0)


def test_short_only_equal_negative_weights_selected_by_threshold():
    result = ResearchPortfolioConstructionService().construct(
        strategy(ResearchStrategyDirection.SHORT_ONLY),
        panel(row(3, 0.1), row(1, 0.2), row(2, 0.7)),
        AS_OF,
    )

    assert result.status is ResearchPortfolioConstructionStatus.CONSTRUCTED
    assert [p.target_weight for p in result.positions] == pytest.approx([-0.5, -0.5])
    assert all(p.side is ResearchPortfolioPositionSide.SHORT for p in result.positions)
    assert result.gross_exposure == pytest.approx(1.0)
    assert result.net_exposure == pytest.approx(-1.0)


def test_long_short_is_equal_weighted_and_dollar_neutral():
    result = ResearchPortfolioConstructionService().construct(
        strategy(ResearchStrategyDirection.LONG_SHORT),
        panel(row(1, 0.9), row(2, 0.8), row(3, 0.2), row(4, 0.1)),
        AS_OF,
    )

    assert result.status is ResearchPortfolioConstructionStatus.CONSTRUCTED
    assert [(p.security_id, p.target_weight) for p in result.positions] == [
        (1, 0.5),
        (2, 0.5),
        (3, -0.5),
        (4, -0.5),
    ]
    assert result.gross_exposure == pytest.approx(2.0)
    assert result.net_exposure == pytest.approx(0.0)


def test_long_short_requires_both_legs():
    result = ResearchPortfolioConstructionService().construct(
        strategy(ResearchStrategyDirection.LONG_SHORT),
        panel(row(1, 0.9), row(2, 0.7)),
        AS_OF,
    )

    assert result.status is ResearchPortfolioConstructionStatus.INCOMPLETE_LONG_SHORT
    assert result.positions == ()
    assert result.long_count == 1
    assert result.short_count == 0


def test_no_eligible_securities_is_explicit():
    result = ResearchPortfolioConstructionService().construct(
        strategy(), panel(row(1, 0.5), row(2, 0.7)), AS_OF
    )
    assert result.status is ResearchPortfolioConstructionStatus.NO_ELIGIBLE_SECURITIES
    assert result.positions == ()
    assert result.gross_exposure == 0.0
    assert result.net_exposure == 0.0


def test_only_requested_as_of_is_constructed():
    later = datetime(2026, 1, 3, 15, 30, tzinfo=timezone.utc)
    result = ResearchPortfolioConstructionService().construct(
        strategy(), panel(row(1, 0.9, AS_OF), row(2, 0.95, later)), AS_OF
    )
    assert [p.security_id for p in result.positions] == [1]


def test_preserves_strategy_and_signal_identity():
    result = ResearchPortfolioConstructionService().construct(
        strategy(), panel(row(1, 0.9)), AS_OF
    )
    assert result.strategy_key == "quality"
    assert result.strategy_definition_version == "1"
    assert result.signal_identity == ("quality_signal", "1")
    assert result.as_of == AS_OF


def test_rejects_signal_identity_mismatch():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstructionService().construct(
            strategy(), panel(row(1, 0.9), identity=("other_signal", "1")), AS_OF
        )


def test_rejects_naive_as_of():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstructionService().construct(
            strategy(), panel(row(1, 0.9)), datetime(2026, 1, 2, 15, 30)
        )


def test_rejects_empty_signal_panel():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstructionService().construct(strategy(), panel(), AS_OF)


def test_rejects_duplicate_security_as_of():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstructionService().construct(
            strategy(), panel(row(1, 0.9), row(1, 0.95)), AS_OF
        )


def test_rejects_score_outside_range():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstructionService().construct(
            strategy(), panel(row(1, 1.1)), AS_OF
        )


def test_threshold_comparison_is_inclusive():
    result = ResearchPortfolioConstructionService().construct(
        strategy(), panel(row(1, 0.8)), AS_OF
    )
    assert len(result.positions) == 1
    assert result.positions[0].target_weight == 1.0


def test_positions_are_deterministically_ordered():
    result = ResearchPortfolioConstructionService().construct(
        strategy(), panel(row(10, 0.9), row(2, 0.9), row(7, 0.9)), AS_OF
    )
    assert [p.security_id for p in result.positions] == [2, 7, 10]


def test_signal_score_is_preserved_in_position():
    result = ResearchPortfolioConstructionService().construct(
        strategy(), panel(row(1, 0.91)), AS_OF
    )
    assert result.positions[0].signal_score == pytest.approx(0.91)
