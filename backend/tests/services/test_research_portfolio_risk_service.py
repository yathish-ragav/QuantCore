from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionStatus,
    ResearchPortfolioPosition,
    ResearchPortfolioPositionSide,
)
from quantcore.services.research_portfolio_risk_service import ResearchPortfolioRiskService

AS_OF = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


def position(security_id, weight, side):
    return ResearchPortfolioPosition(
        symbol=f"T{security_id}", security_id=security_id, as_of=AS_OF,
        signal_score=0.5, side=side, target_weight=weight,
    )


def portfolio(*positions, status=ResearchPortfolioConstructionStatus.CONSTRUCTED):
    long_count = sum(p.target_weight > 0 for p in positions)
    short_count = sum(p.target_weight < 0 for p in positions)
    gross = sum(abs(p.target_weight) for p in positions)
    return ResearchPortfolio(
        strategy_key="quality", strategy_definition_version="1",
        signal_identity=("quality_signal", "1"), as_of=AS_OF, status=status,
        positions=tuple(positions), eligible_count=len(positions),
        long_count=long_count, short_count=short_count,
        gross_exposure=gross, net_exposure=sum(p.target_weight for p in positions),
        construction="TEST",
    )


def test_long_short_exposures():
    snapshot = ResearchPortfolioRiskService().snapshot(
        portfolio(position(1, 0.5, ResearchPortfolioPositionSide.LONG),
                  position(2, 0.5, ResearchPortfolioPositionSide.LONG),
                  position(3, -0.5, ResearchPortfolioPositionSide.SHORT),
                  position(4, -0.5, ResearchPortfolioPositionSide.SHORT))
    )
    assert snapshot.gross_exposure == pytest.approx(2.0)
    assert snapshot.net_exposure == pytest.approx(0.0)
    assert snapshot.long_exposure == pytest.approx(1.0)
    assert snapshot.short_exposure == pytest.approx(1.0)
    assert snapshot.net_to_gross_exposure == pytest.approx(0.0)


def test_position_counts_and_max_weight():
    snapshot = ResearchPortfolioRiskService().snapshot(
        portfolio(position(1, 0.7, ResearchPortfolioPositionSide.LONG),
                  position(2, 0.3, ResearchPortfolioPositionSide.LONG))
    )
    assert snapshot.position_count == 2
    assert snapshot.long_count == 2
    assert snapshot.short_count == 0
    assert snapshot.max_abs_position_weight == pytest.approx(0.7)


def test_hhi_and_effective_position_count():
    snapshot = ResearchPortfolioRiskService().snapshot(
        portfolio(position(1, 0.5, ResearchPortfolioPositionSide.LONG),
                  position(2, 0.5, ResearchPortfolioPositionSide.LONG))
    )
    assert snapshot.hhi == pytest.approx(0.5)
    assert snapshot.effective_position_count == pytest.approx(2.0)
    assert snapshot.long_hhi == pytest.approx(0.5)
    assert snapshot.long_effective_position_count == pytest.approx(2.0)


def test_long_and_short_concentration_are_separate():
    snapshot = ResearchPortfolioRiskService().snapshot(
        portfolio(position(1, 0.8, ResearchPortfolioPositionSide.LONG),
                  position(2, 0.2, ResearchPortfolioPositionSide.LONG),
                  position(3, -1.0, ResearchPortfolioPositionSide.SHORT))
    )
    assert snapshot.long_hhi == pytest.approx(0.68)
    assert snapshot.short_hhi == pytest.approx(1.0)
    assert snapshot.short_effective_position_count == pytest.approx(1.0)


def test_empty_constructed_portfolio_has_zero_metrics():
    snapshot = ResearchPortfolioRiskService().snapshot(portfolio())
    assert snapshot.position_count == 0
    assert snapshot.gross_exposure == 0.0
    assert snapshot.net_exposure == 0.0
    assert snapshot.hhi == 0.0
    assert snapshot.effective_position_count == 0.0


def test_provenance_is_preserved():
    snapshot = ResearchPortfolioRiskService().snapshot(
        portfolio(position(1, 1.0, ResearchPortfolioPositionSide.LONG))
    )
    assert snapshot.strategy_key == "quality"
    assert snapshot.strategy_definition_version == "1"
    assert snapshot.signal_identity == ("quality_signal", "1")
    assert snapshot.as_of == AS_OF


def test_non_constructed_portfolio_is_rejected():
    with pytest.raises(InvalidInputError, match="constructed target portfolios"):
        ResearchPortfolioRiskService().snapshot(
            portfolio(position(1, 1.0, ResearchPortfolioPositionSide.LONG),
                      status=ResearchPortfolioConstructionStatus.NO_ELIGIBLE_SECURITIES)
        )


def test_non_finite_weight_is_rejected():
    with pytest.raises(InvalidInputError, match="finite"):
        ResearchPortfolioRiskService().snapshot(
            portfolio(position(1, float("nan"), ResearchPortfolioPositionSide.LONG))
        )
