from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionStatus,
    ResearchPortfolioPosition,
    ResearchPortfolioPositionSide,
)
from quantcore.services.research_portfolio_stress_service import (
    ResearchPortfolioStressService,
    ResearchStressScenarioDefinition,
)

AS_OF = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


def position(security_id, weight, side):
    return ResearchPortfolioPosition(
        symbol=f"T{security_id}", security_id=security_id, as_of=AS_OF,
        signal_score=0.5, side=side, target_weight=weight,
    )


def portfolio(*positions, status=ResearchPortfolioConstructionStatus.CONSTRUCTED):
    return ResearchPortfolio(
        strategy_key="quality", strategy_definition_version="1",
        signal_identity=("quality_signal", "1"), as_of=AS_OF, status=status,
        positions=tuple(positions), eligible_count=len(positions),
        long_count=sum(p.target_weight > 0 for p in positions),
        short_count=sum(p.target_weight < 0 for p in positions),
        gross_exposure=sum(abs(p.target_weight) for p in positions),
        net_exposure=sum(p.target_weight for p in positions), construction="TEST",
    )


def scenario(shocks, default=None):
    return ResearchStressScenarioDefinition(
        scenario_key="market_crash", definition_version="1",
        shocks_by_security=shocks, default_shock=default,
    )


def test_long_short_stress_contributions_are_directional():
    result = ResearchPortfolioStressService().apply(
        portfolio(position(1, 0.6, ResearchPortfolioPositionSide.LONG),
                  position(2, -0.4, ResearchPortfolioPositionSide.SHORT)),
        scenario({1: -0.20, 2: -0.30}),
    )
    assert result.portfolio_return == pytest.approx(0.0)
    assert result.impacts[0].contribution == pytest.approx(-0.12)
    assert result.impacts[1].contribution == pytest.approx(0.12)


def test_default_shock_supports_broad_market_scenario():
    result = ResearchPortfolioStressService().apply(
        portfolio(position(1, 0.7, ResearchPortfolioPositionSide.LONG),
                  position(2, 0.3, ResearchPortfolioPositionSide.LONG)),
        scenario({}, default=-0.25),
        portfolio_value=1_000_000,
    )
    assert result.portfolio_return == pytest.approx(-0.25)
    assert result.pnl_amount == pytest.approx(-250_000)
    assert result.stressed_value == pytest.approx(750_000)
    assert result.shocked_position_count == 2


def test_security_specific_shock_overrides_default():
    result = ResearchPortfolioStressService().apply(
        portfolio(position(1, 0.5, ResearchPortfolioPositionSide.LONG),
                  position(2, 0.5, ResearchPortfolioPositionSide.LONG)),
        scenario({1: -0.40}, default=-0.10),
    )
    assert result.portfolio_return == pytest.approx(-0.25)
    assert result.impacts[0].shock == pytest.approx(-0.40)
    assert result.impacts[1].shock == pytest.approx(-0.10)


def test_missing_explicit_shock_is_rejected_without_default():
    with pytest.raises(InvalidInputError, match="Missing stress shock"):
        ResearchPortfolioStressService().apply(
            portfolio(position(1, 1.0, ResearchPortfolioPositionSide.LONG)),
            scenario({}),
        )


def test_stress_result_is_deterministic():
    target = portfolio(position(1, 0.5, ResearchPortfolioPositionSide.LONG),
                       position(2, -0.5, ResearchPortfolioPositionSide.SHORT))
    definition = scenario({1: -0.20, 2: 0.10})
    service = ResearchPortfolioStressService()
    assert service.apply(target, definition) == service.apply(target, definition)


def test_provenance_is_preserved():
    result = ResearchPortfolioStressService().apply(
        portfolio(position(1, 1.0, ResearchPortfolioPositionSide.LONG)),
        scenario({1: -0.10}),
    )
    assert result.scenario_identity == ("market_crash", "1")
    assert result.strategy_key == "quality"
    assert result.strategy_definition_version == "1"
    assert result.signal_identity == ("quality_signal", "1")
    assert result.as_of == AS_OF


def test_invalid_shock_below_minus_one_is_rejected():
    with pytest.raises(InvalidInputError, match="greater than or equal to -100%"):
        scenario({1: -1.01})


def test_non_constructed_portfolio_is_rejected():
    with pytest.raises(InvalidInputError, match="constructed target portfolio"):
        ResearchPortfolioStressService().apply(
            portfolio(position(1, 1.0, ResearchPortfolioPositionSide.LONG),
                      status=ResearchPortfolioConstructionStatus.NO_ELIGIBLE_SECURITIES),
            scenario({1: -0.10}),
        )


def test_invalid_portfolio_value_is_rejected():
    with pytest.raises(InvalidInputError, match="finite positive"):
        ResearchPortfolioStressService().apply(
            portfolio(position(1, 1.0, ResearchPortfolioPositionSide.LONG)),
            scenario({1: -0.10}),
            portfolio_value=0,
        )
