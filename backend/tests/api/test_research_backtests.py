from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.core.enums import PriceBasis
from quantcore.services.research_backtest_product_service import ResearchBacktestProductResult
from quantcore.services.research_backtest_service import (
    ResearchBacktest,
    ResearchBacktestPeriod,
    ResearchBacktestPeriodStatus,
    ResearchBacktestStatus,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionStatus,
)
from quantcore.services.research_portfolio_product_service import ResearchPortfolioProductResult
from quantcore.services.research_portfolio_construction_service import ResearchPortfolioPosition, ResearchPortfolioPositionSide
from quantcore.services.research_strategy_service import ResearchStrategyDirection

client = TestClient(app)
AS_OF_0 = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
AS_OF_1 = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_backtest_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def payload():
    return {
        "symbols": ["AAA"],
        "as_ofs": [AS_OF_0.isoformat(), AS_OF_1.isoformat()],
        "dataset_identity": ["dataset", "1"],
        "signal_key": "quality_signal",
        "signal_definition_version": "1",
        "factors": [
            {
                "factor_key": "quality",
                "definition_version": "1",
                "weight": 1.0,
                "higher_is_better": True,
            }
        ],
        "strategy": {
            "strategy_key": "quality_long",
            "definition_version": "1",
            "signal_identity": ["quality_signal", "1"],
            "direction": "LONG_ONLY",
            "long_threshold": 0.8,
        },
        "backtest_key": "quality_backtest",
        "backtest_definition_version": "1",
        "initial_capital": 1000000.0,
        "price_basis": "UNADJUSTED",
        "constraint_key": "basic",
        "constraint_definition_version": "1",
        "max_position_weight": 1.0,
        "max_gross_exposure": 1.0,
        "rebalance_key": "daily",
        "rebalance_definition_version": "1",
        "frequency": "DAILY",
        "cost_key": "tc",
        "cost_definition_version": "1",
        "one_way_cost_bps": 10.0,
    }


def product_result():
    position = ResearchPortfolioPosition(
        symbol="AAA",
        security_id=10,
        as_of=AS_OF_0,
        signal_score=0.9,
        side=ResearchPortfolioPositionSide.LONG,
        target_weight=1.0,
    )
    portfolio = ResearchPortfolio(
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=AS_OF_0,
        status=ResearchPortfolioConstructionStatus.CONSTRUCTED,
        positions=(position,),
        eligible_count=1,
        long_count=1,
        short_count=0,
        gross_exposure=1.0,
        net_exposure=1.0,
        construction="EQUAL_WEIGHT_LONG_ONLY",
    )
    target = ResearchPortfolio(
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=AS_OF_1,
        status=ResearchPortfolioConstructionStatus.CONSTRUCTED,
        positions=(position.__class__(**{**position.__dict__, "as_of": AS_OF_1}),),
        eligible_count=1,
        long_count=1,
        short_count=0,
        gross_exposure=1.0,
        net_exposure=1.0,
        construction="EQUAL_WEIGHT_LONG_ONLY",
    )
    first = ResearchPortfolioProductResult(
        portfolio=portfolio,
        dataset_fingerprint="fp-0",
        dataset_identity=("dataset", "1"),
        signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )
    second = ResearchPortfolioProductResult(
        portfolio=target,
        dataset_fingerprint="fp-1",
        dataset_identity=("dataset", "1"),
        signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )
    period = ResearchBacktestPeriod(
        period_start=AS_OF_0,
        period_end=AS_OF_1,
        starting_equity=1000000.0,
        ending_equity=1100000.0,
        gross_return=0.101,
        transaction_cost_fraction=0.001,
        net_return=0.1,
        turnover=1.0,
        status=ResearchBacktestPeriodStatus.COMPLETED,
    )
    backtest = ResearchBacktest(
        backtest_key="quality_backtest",
        backtest_definition_version="1",
        strategy_identity=("quality_long", "1"),
        constraint_identity=("basic", "1"),
        rebalance_identity=("daily", "1"),
        transaction_cost_identity=("tc", "1"),
        start_as_of=AS_OF_0,
        end_as_of=AS_OF_1,
        initial_capital=1000000.0,
        final_equity=1100000.0,
        total_return=0.1,
        price_basis=PriceBasis.UNADJUSTED,
        periods=(period,),
        status=ResearchBacktestStatus.COMPLETED,
    )
    return ResearchBacktestProductResult(
        backtest=backtest,
        target_portfolios=(first, second),
    )


@patch("quantcore.api.dependencies.ResearchBacktestProductService")
def test_run_research_backtest_returns_stable_contract(mock_service):
    service = Mock()
    service.run.return_value = product_result()
    mock_service.return_value = service

    response = client.post("/api/v1/research/backtests", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["backtest_key"] == "quality_backtest"
    assert body["strategy_identity"] == ["quality_long", "1"]
    assert body["constraint_identity"] == ["basic", "1"]
    assert body["rebalance_identity"] == ["daily", "1"]
    assert body["transaction_cost_identity"] == ["tc", "1"]
    assert body["total_return"] == pytest.approx(0.1)
    assert body["target_portfolios"][0]["dataset_fingerprint"] == "fp-0"
    assert body["target_portfolios"][1]["dataset_fingerprint"] == "fp-1"
    assert len(body["periods"]) == 1
    service.run.assert_called_once()
    call = service.run.call_args.kwargs
    assert call["symbols"] == ["AAA"]
    assert call["as_ofs"] == [
        AS_OF_0,
        AS_OF_1,
    ]
    assert call["backtest_definition"].identity == ("quality_backtest", "1")
    assert call["backtest_definition"].strategy_identity == ("quality_long", "1")
    assert call["constraint_definition"].identity == ("basic", "1")
    assert call["rebalance_definition"].identity == ("daily", "1")
    assert call["transaction_cost_definition"].identity == ("tc", "1")


def test_run_research_backtest_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post("/api/v1/research/backtests", json=payload())
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal
    assert response.status_code == 401


def test_run_research_backtest_bounds_request_size():
    body = payload()
    body["symbols"] = [f"S{i}" for i in range(101)]
    response = client.post("/api/v1/research/backtests", json=body)
    assert response.status_code in {400, 422}


def test_run_research_backtest_requires_ordered_as_ofs():
    body = payload()
    body["as_ofs"] = [AS_OF_1.isoformat(), AS_OF_0.isoformat()]
    response = client.post("/api/v1/research/backtests", json=body)
    assert response.status_code == 422
