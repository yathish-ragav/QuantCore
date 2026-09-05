from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionStatus,
    ResearchPortfolioPosition,
    ResearchPortfolioPositionSide,
)
from quantcore.services.research_portfolio_factor_risk_service import (
    ResearchPortfolioFactorRiskService,
)

AS_OF = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


def factor_row(security_id, normalized_rank):
    value = ResearchFactorValue(
        factor_key="quality",
        definition_version="1",
        symbol=f"T{security_id}",
        security_id=security_id,
        as_of=AS_OF,
        value_numeric=normalized_rank,
    )
    return ResearchFactorRankRow(
        symbol=f"T{security_id}",
        security_id=security_id,
        as_of=AS_OF,
        factor_value=value,
        rank=1.0,
        normalized_rank=normalized_rank,
    )


def panel(*rows):
    return ResearchFactorRankedPanel(
        factor_key="quality",
        definition_version="1",
        rows=tuple(rows),
        ranking="average_tie",
        higher_is_better=True,
    )


def portfolio(*positions, status=ResearchPortfolioConstructionStatus.CONSTRUCTED):
    return ResearchPortfolio(
        strategy_key="quality_strategy",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=AS_OF,
        status=status,
        positions=tuple(positions),
        eligible_count=len(positions),
        long_count=sum(p.target_weight > 0.0 for p in positions),
        short_count=sum(p.target_weight < 0.0 for p in positions),
        gross_exposure=sum(abs(p.target_weight) for p in positions),
        net_exposure=sum(p.target_weight for p in positions),
        construction="TEST",
    )


def position(security_id, weight):
    side = (
        ResearchPortfolioPositionSide.LONG
        if weight > 0.0
        else ResearchPortfolioPositionSide.SHORT
    )
    return ResearchPortfolioPosition(
        symbol=f"T{security_id}",
        security_id=security_id,
        as_of=AS_OF,
        signal_score=0.5,
        side=side,
        target_weight=weight,
    )


def test_rank_based_factor_exposure_is_deterministic():
    service = ResearchPortfolioFactorRiskService()
    target = portfolio(position(1, 0.5), position(2, -0.5))
    inputs = {("quality", "1"): panel(factor_row(1, 1.0), factor_row(2, 0.0))}

    first = service.snapshot(target, inputs)
    second = service.snapshot(target, inputs)

    assert first == second
    exposure = first.factor_exposures[0]
    assert exposure.exposure == pytest.approx(1.0)
    assert exposure.long_exposure == pytest.approx(0.5)
    assert exposure.short_exposure == pytest.approx(0.5)
    assert exposure.gross_factor_exposure == pytest.approx(1.0)
    assert exposure.gross_normalized_exposure == pytest.approx(1.0)


def test_short_high_factor_exposure_is_negative():
    target = portfolio(position(1, -1.0))
    result = ResearchPortfolioFactorRiskService().snapshot(
        target,
        {("quality", "1"): panel(factor_row(1, 1.0))},
    )

    exposure = result.factor_exposures[0]
    assert exposure.exposure == pytest.approx(-1.0)
    assert exposure.long_exposure == pytest.approx(0.0)
    assert exposure.short_exposure == pytest.approx(-1.0)
    assert exposure.gross_factor_exposure == pytest.approx(1.0)
    assert exposure.gross_normalized_exposure == pytest.approx(-1.0)


def test_long_only_factor_exposure_uses_centered_rank():
    target = portfolio(position(1, 0.75), position(2, 0.25))
    result = ResearchPortfolioFactorRiskService().snapshot(
        target,
        {("quality", "1"): panel(factor_row(1, 1.0), factor_row(2, 0.0))},
    )

    exposure = result.factor_exposures[0]
    assert exposure.exposure == pytest.approx(0.5)
    assert exposure.long_exposure == pytest.approx(0.5)
    assert exposure.short_exposure == pytest.approx(0.0)
    assert exposure.gross_normalized_exposure == pytest.approx(0.5)


def test_multiple_factor_identities_are_sorted_and_preserved():
    target = portfolio(position(1, 1.0))
    quality = panel(factor_row(1, 1.0))
    value = ResearchFactorRankedPanel(
        factor_key="value",
        definition_version="2",
        rows=(ResearchFactorRankRow(
            symbol="T1",
            security_id=1,
            as_of=AS_OF,
            factor_value=ResearchFactorValue(
                factor_key="value",
                definition_version="2",
                symbol="T1",
                security_id=1,
                as_of=AS_OF,
                value_numeric=0.0,
            ),
            rank=1.0,
            normalized_rank=0.0,
        ),),
        ranking="average_tie",
        higher_is_better=True,
    )

    result = ResearchPortfolioFactorRiskService().snapshot(
        target,
        {("value", "2"): value, ("quality", "1"): quality},
    )

    assert [x.factor_identity for x in result.factor_exposures] == [
        ("quality", "1"),
        ("value", "2"),
    ]


def test_missing_position_factor_observation_is_rejected():
    target = portfolio(position(1, 1.0))
    with pytest.raises(InvalidInputError, match="Missing factor observation"):
        ResearchPortfolioFactorRiskService().snapshot(
            target,
            {("quality", "1"): panel(factor_row(2, 1.0))},
        )


def test_identity_mismatch_is_rejected():
    target = portfolio(position(1, 1.0))
    wrong_panel = ResearchFactorRankedPanel(
        factor_key="value",
        definition_version="1",
        rows=(factor_row(1, 1.0),),
        ranking="average_tie",
        higher_is_better=True,
    )
    with pytest.raises(InvalidInputError, match="identity"):
        ResearchPortfolioFactorRiskService().snapshot(
            target,
            {("quality", "1"): wrong_panel},
        )


def test_non_constructed_portfolio_is_rejected():
    target = portfolio(
        position(1, 1.0),
        status=ResearchPortfolioConstructionStatus.NO_ELIGIBLE_SECURITIES,
    )
    with pytest.raises(InvalidInputError, match="constructed"):
        ResearchPortfolioFactorRiskService().snapshot(
            target,
            {("quality", "1"): panel(factor_row(1, 1.0))},
        )


def test_duplicate_portfolio_security_is_rejected():
    target = portfolio(position(1, 0.5), position(1, 0.5))
    with pytest.raises(InvalidInputError, match="unique portfolio security"):
        ResearchPortfolioFactorRiskService().snapshot(
            target,
            {("quality", "1"): panel(factor_row(1, 1.0))},
        )


def test_empty_factor_panels_are_rejected():
    target = portfolio(position(1, 1.0))
    empty = ResearchFactorRankedPanel(
        factor_key="quality",
        definition_version="1",
        rows=(),
        ranking="average_tie",
        higher_is_better=True,
    )
    with pytest.raises(InvalidInputError, match="must not be empty"):
        ResearchPortfolioFactorRiskService().snapshot(target, {("quality", "1"): empty})


def test_position_as_of_must_match_portfolio():
    target_position = ResearchPortfolioPosition(
        symbol="T1",
        security_id=1,
        as_of=datetime(2026, 1, 3, 15, 30, tzinfo=timezone.utc),
        signal_score=0.5,
        side=ResearchPortfolioPositionSide.LONG,
        target_weight=1.0,
    )
    target = portfolio(target_position)
    with pytest.raises(InvalidInputError, match="position as_of"):
        ResearchPortfolioFactorRiskService().snapshot(
            target,
            {("quality", "1"): panel(factor_row(1, 1.0))},
        )


def test_provenance_is_preserved():
    target = portfolio(position(1, 1.0))
    result = ResearchPortfolioFactorRiskService().snapshot(
        target,
        {("quality", "1"): panel(factor_row(1, 0.75))},
    )

    assert result.strategy_key == "quality_strategy"
    assert result.strategy_definition_version == "1"
    assert result.signal_identity == ("quality_signal", "1")
    assert result.as_of == AS_OF
    assert result.position_count == 1
    assert result.factor_exposures[0].factor_observation_count == 1
