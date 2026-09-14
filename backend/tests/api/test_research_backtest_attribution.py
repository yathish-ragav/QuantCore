from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.core.enums import PriceBasis
from quantcore.services.research_backtest_attribution_product_service import (
    ResearchBacktestAttributionProductResult,
)
from quantcore.services.research_backtest_attribution_service import (
    ResearchBacktestAttribution,
    ResearchBacktestPeriodAttribution,
    ResearchBacktestPositionAttribution,
)
from quantcore.services.research_backtest_product_service import ResearchBacktestProductResult
from quantcore.services.research_backtest_service import ResearchBacktest

client = TestClient(app)
AS_OF_0 = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
AS_OF_1 = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)


def principal():
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def auth_override():
    app.dependency_overrides[get_current_principal] = principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def payload():
    return {
        "symbols": ["AAA"],
        "as_ofs": [AS_OF_0.isoformat(), AS_OF_1.isoformat()],
        "dataset_identity": ["dataset", "1"],
        "signal_key": "quality_signal",
        "signal_definition_version": "1",
        "factors": [{"factor_key": "quality", "definition_version": "1", "weight": 1.0, "higher_is_better": True}],
        "strategy": {"strategy_key": "quality_long", "definition_version": "1", "signal_identity": ["quality_signal", "1"], "direction": "LONG_ONLY", "long_threshold": 0.8},
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
    target = Mock()
    target.portfolio.as_of = AS_OF_0
    target.dataset_fingerprint = "fp-0"
    target.dataset_identity = ("dataset", "1")
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
        periods=(
            Mock(
                period_start=AS_OF_0,
                period_end=AS_OF_1,
                starting_equity=1000000.0,
                ending_equity=1100000.0,
                gross_return=0.105,
                transaction_cost_fraction=-0.005,
                net_return=0.1,
                turnover=0.5,
                status=Mock(value="COMPLETED"),
            ),
        ),
        status=Mock(value="COMPLETED"),
    )
    position = ResearchBacktestPositionAttribution(
        period_start=AS_OF_0,
        period_end=AS_OF_1,
        symbol="AAA",
        security_id=1,
        target_weight=1.0,
        security_return=0.105,
        gross_contribution=0.105,
        return_contribution=0.105,
    )
    period = ResearchBacktestPeriodAttribution(
        period_start=AS_OF_0,
        period_end=AS_OF_1,
        starting_equity=1000000.0,
        ending_equity=1100000.0,
        gross_return=0.105,
        transaction_cost_drag=-0.005,
        net_return=0.1,
        long_contribution=0.105,
        short_contribution=0.0,
        return_contribution=0.105,
        transaction_cost_return_contribution=-0.005,
        position_contributions=(position,),
    )
    attribution = ResearchBacktestAttribution(
        backtest_identity=("quality_backtest", "1"),
        periods=(period,),
        total_gross_return=0.105,
        total_transaction_cost_drag=-0.005,
        total_net_return=0.1,
        total_long_contribution=0.105,
        total_short_contribution=0.0,
        total_transaction_cost_return_contribution=-0.005,
    )
    return ResearchBacktestAttributionProductResult(
        backtest=ResearchBacktestProductResult(
            backtest=backtest,
            target_portfolios=(target,),
            price_history_by_security={},
        ),
        attribution=attribution,
    )


@patch("quantcore.api.dependencies.ResearchBacktestAttributionProductService")
def test_attribution_endpoint_returns_realized_contributions(mock_service):
    service = Mock()
    service.analyze.return_value = product_result()
    mock_service.return_value = service

    response = client.post("/api/v1/research/backtests/attribution", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["backtest_key"] == "quality_backtest"
    assert body["total_gross_return"] == pytest.approx(0.105)
    assert body["total_transaction_cost_drag"] == pytest.approx(-0.005)
    assert body["periods"][0]["position_contributions"][0]["symbol"] == "AAA"
    assert body["target_portfolios"][0]["dataset_fingerprint"] == "fp-0"
    service.analyze.assert_called_once()


def test_attribution_endpoint_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post("/api/v1/research/backtests/attribution", json=payload())
    finally:
        app.dependency_overrides[get_current_principal] = principal
    assert response.status_code == 401


def test_attribution_endpoint_bounds_request_size():
    body = payload()
    body["symbols"] = [f"S{i}" for i in range(101)]
    response = client.post("/api/v1/research/backtests/attribution", json=body)
    assert response.status_code in {400, 422}
