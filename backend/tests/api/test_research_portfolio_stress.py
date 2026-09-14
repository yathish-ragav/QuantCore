from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductResult,
    ResearchPortfolioStressProductResult,
)
from quantcore.services.research_portfolio_stress_service import ResearchPortfolioStressImpact

client = TestClient(app)
AS_OF = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_portfolio_stress_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def payload():
    return {
        "symbols": ["AAA"],
        "as_ofs": [AS_OF.isoformat()],
        "target_as_of": AS_OF.isoformat(),
        "dataset_identity": ["dataset", "1"],
        "signal_key": "quality_signal",
        "signal_definition_version": "1",
        "factors": [{
            "factor_key": "quality",
            "definition_version": "1",
            "weight": 1.0,
            "higher_is_better": True,
        }],
        "strategy": {
            "strategy_key": "quality_long",
            "definition_version": "1",
            "signal_identity": ["quality_signal", "1"],
            "direction": "LONG_ONLY",
            "long_threshold": 0.8,
        },
        "scenario_key": "selloff",
        "scenario_definition_version": "1",
        "shocks_by_security": {"1": -0.10},
        "portfolio_value": 100000.0,
    }


def test_stress_research_portfolio_returns_stable_contract():
    impact = ResearchPortfolioStressImpact(
        security_id=1, symbol="AAA", target_weight=1.0, shock=-0.10, contribution=-0.10,
    )
    stress = Mock(
        scenario_identity=("selloff", "1"),
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=AS_OF,
        position_count=1, shocked_position_count=1, portfolio_return=-0.10,
        portfolio_value=100000.0, pnl_amount=-10000.0, stressed_value=90000.0,
        best_position_contribution=-0.10, worst_position_contribution=-0.10, impacts=(impact,),
    )
    result = ResearchPortfolioStressProductResult(
        portfolio=ResearchPortfolioProductResult(
            portfolio=Mock(), dataset_fingerprint="dataset-fp",
            dataset_identity=("dataset", "1"),
            signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
        ),
        stress=stress,
    )
    product_service = Mock()
    product_service.construct_with_stress.return_value = result

    with patch("quantcore.api.dependencies.ResearchPortfolioProductService", return_value=product_service):
        response = client.post("/api/v1/research/portfolios/stress", json=payload())

    assert response.status_code == 200
    assert response.json() == {
        "scenario_key": "selloff", "scenario_definition_version": "1",
        "strategy_key": "quality_long", "strategy_definition_version": "1",
        "signal_identity": ["quality_signal", "1"],
        "as_of": "2026-08-20T15:30:00Z", "position_count": 1,
        "shocked_position_count": 1, "portfolio_return": -0.10,
        "portfolio_value": 100000.0, "pnl_amount": -10000.0, "stressed_value": 90000.0,
        "best_position_contribution": -0.10, "worst_position_contribution": -0.10,
        "dataset_fingerprint": "dataset-fp", "dataset_identity": ["dataset", "1"],
        "signal_construction": "WEIGHTED_NORMALIZED_RANK_AVERAGE",
        "impacts": [{"security_id": 1, "symbol": "AAA", "target_weight": 1.0,
                     "shock": -0.10, "contribution": -0.10}],
    }
    product_service.construct_with_stress.assert_called_once()


def test_stress_research_portfolio_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post("/api/v1/research/portfolios/stress", json=payload())
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal
    assert response.status_code == 401


def test_stress_research_portfolio_bounds_request_size():
    body = payload()
    body["symbols"] = [f"S{i}" for i in range(101)]
    response = client.post("/api/v1/research/portfolios/stress", json=body)
    assert response.status_code in {400, 422}


def test_stress_research_portfolio_bounds_explicit_shocks():
    body = payload()
    body["shocks_by_security"] = {str(i): -0.01 for i in range(101)}
    response = client.post("/api/v1/research/portfolios/stress", json=body)
    assert response.status_code in {400, 422}
