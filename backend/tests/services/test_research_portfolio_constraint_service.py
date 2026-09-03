from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
    ResearchPortfolioConstraintService,
    ResearchPortfolioConstraintStatus,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolioConstructionService,
)
from quantcore.services.research_signal_service import ResearchSignalPanel, ResearchSignalRow
from quantcore.services.research_strategy_service import ResearchStrategyDefinition, ResearchStrategyDirection


AS_OF = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


def strategy(direction=ResearchStrategyDirection.LONG_SHORT):
    return ResearchStrategyDefinition(
        strategy_key="quality",
        definition_version="1",
        signal_identity=("quality_signal", "1"),
        direction=direction,
        long_threshold=0.8 if direction is not ResearchStrategyDirection.SHORT_ONLY else None,
        short_threshold=0.2 if direction is not ResearchStrategyDirection.LONG_ONLY else None,
    )


def panel(*rows):
    return ResearchSignalPanel(
        signal_key="quality_signal",
        definition_version="1",
        factor_identities=(),
        rows=tuple(rows),
        construction="TEST",
    )


def row(security_id, score):
    return ResearchSignalRow(
        symbol=f"T{security_id}",
        security_id=security_id,
        as_of=AS_OF,
        score=score,
        centered_score=2 * score - 1,
        contributions=(),
    )


def portfolio():
    return ResearchPortfolioConstructionService().construct(
        strategy(),
        panel(row(1, 0.9), row(2, 0.85), row(3, 0.2), row(4, 0.1)),
        AS_OF,
    )


def test_definition_requires_at_least_one_constraint():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstraintDefinition("risk", "1")


def test_definition_normalizes_and_exposes_identity():
    definition = ResearchPortfolioConstraintDefinition(
        " risk ", " 1 ", max_position_weight="0.10", description=" limits "
    )
    assert definition.constraint_key == "risk"
    assert definition.definition_version == "1"
    assert definition.identity == ("risk", "1")
    assert definition.max_position_weight == pytest.approx(0.10)
    assert definition.description == "limits"


def test_definition_rejects_negative_non_net_limits():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstraintDefinition("risk", "1", max_gross_exposure=-1)


def test_definition_allows_signed_net_limits():
    definition = ResearchPortfolioConstraintDefinition(
        "risk", "1", min_net_exposure=-0.1, max_net_exposure=0.1
    )
    assert definition.min_net_exposure == pytest.approx(-0.1)
    assert definition.max_net_exposure == pytest.approx(0.1)


def test_definition_rejects_inverted_net_range():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstraintDefinition(
            "risk", "1", min_net_exposure=0.2, max_net_exposure=0.1
        )


def test_passes_when_all_constraints_are_satisfied():
    result = ResearchPortfolioConstraintService().validate(
        portfolio(),
        ResearchPortfolioConstraintDefinition(
            "risk", "1", max_position_weight=0.5, max_gross_exposure=2.0,
            min_net_exposure=-0.1, max_net_exposure=0.1,
            max_long_exposure=1.0, max_short_exposure=1.0,
        ),
    )
    assert result.status is ResearchPortfolioConstraintStatus.PASSED
    assert result.violations == ()
    assert result.observed_max_position_weight == pytest.approx(0.5)
    assert result.observed_gross_exposure == pytest.approx(2.0)
    assert result.observed_net_exposure == pytest.approx(0.0)
    assert result.observed_long_exposure == pytest.approx(1.0)
    assert result.observed_short_exposure == pytest.approx(1.0)


def test_reports_position_and_gross_violations():
    result = ResearchPortfolioConstraintService().validate(
        portfolio(),
        ResearchPortfolioConstraintDefinition(
            "risk", "1", max_position_weight=0.4, max_gross_exposure=1.5
        ),
    )
    assert result.status is ResearchPortfolioConstraintStatus.VIOLATED
    assert [(v.constraint, v.observed_value, v.limit) for v in result.violations] == [
        ("max_position_weight", 0.5, 0.4),
        ("max_gross_exposure", 2.0, 1.5),
    ]


def test_reports_net_and_leg_exposure_violations():
    long_portfolio = ResearchPortfolioConstructionService().construct(
        ResearchStrategyDefinition(
            strategy_key="quality",
            definition_version="1",
            signal_identity=("quality_signal", "1"),
            direction=ResearchStrategyDirection.LONG_ONLY,
            long_threshold=0.8,
        ),
        panel(row(1, 0.9), row(2, 0.85)),
        AS_OF,
    )
    result = ResearchPortfolioConstraintService().validate(
        long_portfolio,
        ResearchPortfolioConstraintDefinition(
            "risk", "1", min_net_exposure=1.1, max_net_exposure=2.0, max_long_exposure=0.5
        ),
    )
    assert result.status is ResearchPortfolioConstraintStatus.VIOLATED
    assert {v.constraint for v in result.violations} == {
        "min_net_exposure", "max_long_exposure"
    }


def test_reports_max_net_exposure_violation():
    result = ResearchPortfolioConstraintService().validate(
        portfolio(),
        ResearchPortfolioConstraintDefinition("risk", "1", max_net_exposure=-0.1),
    )
    assert result.status is ResearchPortfolioConstraintStatus.VIOLATED
    assert [(v.constraint, v.observed_value, v.limit) for v in result.violations] == [
        ("max_net_exposure", 0.0, -0.1)
    ]


def test_short_exposure_is_reported_as_positive_magnitude():
    short_portfolio = ResearchPortfolioConstructionService().construct(
        ResearchStrategyDefinition(
            strategy_key="quality",
            definition_version="1",
            signal_identity=("quality_signal", "1"),
            direction=ResearchStrategyDirection.SHORT_ONLY,
            short_threshold=0.2,
        ),
        panel(row(1, 0.1), row(2, 0.2)),
        AS_OF,
    )
    result = ResearchPortfolioConstraintService().validate(
        short_portfolio,
        ResearchPortfolioConstraintDefinition("risk", "1", max_short_exposure=0.5),
    )
    assert result.status is ResearchPortfolioConstraintStatus.VIOLATED
    assert result.observed_short_exposure == pytest.approx(1.0)


def test_constraints_are_inclusive_at_the_limit():
    result = ResearchPortfolioConstraintService().validate(
        portfolio(),
        ResearchPortfolioConstraintDefinition(
            "risk", "1", max_position_weight=0.5, max_gross_exposure=2.0,
            min_net_exposure=0.0, max_net_exposure=0.0,
            max_long_exposure=1.0, max_short_exposure=1.0,
        ),
    )
    assert result.status is ResearchPortfolioConstraintStatus.PASSED


def test_empty_portfolio_passes_exposure_constraints():
    empty = ResearchPortfolioConstructionService().construct(
        ResearchStrategyDefinition(
            strategy_key="quality", definition_version="1",
            signal_identity=("quality_signal", "1"),
            direction=ResearchStrategyDirection.LONG_ONLY, long_threshold=0.8,
        ),
        panel(row(1, 0.5)), AS_OF,
    )
    result = ResearchPortfolioConstraintService().validate(
        empty,
        ResearchPortfolioConstraintDefinition("risk", "1", max_gross_exposure=1.0),
    )
    assert result.status is ResearchPortfolioConstraintStatus.PASSED
    assert result.observed_gross_exposure == 0.0


def test_preserves_portfolio_provenance():
    result = ResearchPortfolioConstraintService().validate(
        portfolio(), ResearchPortfolioConstraintDefinition("risk", "1", max_gross_exposure=2.0)
    )
    assert result.strategy_key == "quality"
    assert result.strategy_definition_version == "1"
    assert result.signal_identity == ("quality_signal", "1")
    assert result.as_of == AS_OF
    assert result.constraint_key == "risk"
    assert result.constraint_definition_version == "1"


def test_rejects_wrong_portfolio_type():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstraintService().validate(object(), ResearchPortfolioConstraintDefinition("risk", "1", max_gross_exposure=1))


def test_rejects_wrong_definition_type():
    with pytest.raises(InvalidInputError):
        ResearchPortfolioConstraintService().validate(portfolio(), object())
