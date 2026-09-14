from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionStatus,
    ResearchPortfolioPosition,
    ResearchPortfolioPositionSide,
)
from quantcore.services.research_portfolio_product_service import ResearchPortfolioProductResult

client = TestClient(app)
AS_OF = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_portfolio_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def payload():
    return {
        "symbols": ["AAA", "BBB"],
        "as_ofs": [AS_OF.isoformat()],
        "target_as_of": AS_OF.isoformat(),
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
    }


def test_construct_research_portfolio_returns_stable_contract():
    portfolio = ResearchPortfolio(
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=AS_OF,
        status=ResearchPortfolioConstructionStatus.CONSTRUCTED,
        positions=(
            ResearchPortfolioPosition(
                symbol="AAA",
                security_id=1,
                as_of=AS_OF,
                signal_score=0.95,
                side=ResearchPortfolioPositionSide.LONG,
                target_weight=1.0,
            ),
        ),
        eligible_count=1,
        long_count=1,
        short_count=0,
        gross_exposure=1.0,
        net_exposure=1.0,
        construction="EQUAL_WEIGHT_LONG_ONLY",
    )
    result = ResearchPortfolioProductResult(
        portfolio=portfolio,
        dataset_fingerprint="dataset-fp",
        dataset_identity=("dataset", "1"),
        signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
    )
    product_service = Mock()
    product_service.construct.return_value = result

    with patch(
        "quantcore.api.dependencies.ResearchPortfolioProductService",
        return_value=product_service,
    ):
        response = client.post("/api/v1/research/portfolios", json=payload())

    assert response.status_code == 200
    assert response.json() == {
        "strategy_key": "quality_long",
        "strategy_definition_version": "1",
        "signal_identity": ["quality_signal", "1"],
        "as_of": "2026-08-20T15:30:00Z",
        "status": "CONSTRUCTED",
        "construction": "EQUAL_WEIGHT_LONG_ONLY",
        "eligible_count": 1,
        "long_count": 1,
        "short_count": 0,
        "gross_exposure": 1.0,
        "net_exposure": 1.0,
        "dataset_fingerprint": "dataset-fp",
        "dataset_identity": ["dataset", "1"],
        "signal_construction": "WEIGHTED_NORMALIZED_RANK_AVERAGE",
        "positions": [
            {
                "symbol": "AAA",
                "security_id": 1,
                "as_of": "2026-08-20T15:30:00Z",
                "signal_score": 0.95,
                "side": "LONG",
                "target_weight": 1.0,
            }
        ],
    }


def test_construct_research_portfolio_requires_target_as_of_from_requested_points():
    body = payload()
    body["target_as_of"] = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc).isoformat()
    response = client.post("/api/v1/research/portfolios", json=body)
    assert response.status_code == 422


def test_construct_research_portfolio_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post("/api/v1/research/portfolios", json=payload())
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal
    assert response.status_code == 401
