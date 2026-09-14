from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioFactorRiskProductResult,
)

client = TestClient(app)
AS_OF = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_portfolio_factor_risk_api():
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


def test_assess_research_portfolio_factor_risk_returns_stable_contract():
    exposure = Mock(
        factor_identity=("quality", "1"),
        as_of=AS_OF,
        position_count=2,
        factor_observation_count=2,
        exposure=0.25,
        long_exposure=0.25,
        short_exposure=0.0,
        gross_factor_exposure=0.5,
        gross_normalized_exposure=0.25,
    )
    snapshot = Mock(
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=AS_OF,
        position_count=2,
        factor_exposures=(exposure,),
    )
    result = ResearchPortfolioFactorRiskProductResult(
        portfolio=Mock(
            dataset_fingerprint="dataset-fp",
            dataset_identity=("dataset", "1"),
            signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
        ),
        factor_risk=snapshot,
    )
    product_service = Mock()
    product_service.construct_with_factor_risk.return_value = result

    with patch(
        "quantcore.api.dependencies.ResearchPortfolioProductService",
        return_value=product_service,
    ):
        response = client.post(
            "/api/v1/research/portfolios/factor-risk",
            json=payload(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "strategy_key": "quality_long",
        "strategy_definition_version": "1",
        "signal_identity": ["quality_signal", "1"],
        "as_of": "2026-08-20T15:30:00Z",
        "position_count": 2,
        "factor_exposures": [
            {
                "factor_identity": ["quality", "1"],
                "as_of": "2026-08-20T15:30:00Z",
                "position_count": 2,
                "factor_observation_count": 2,
                "exposure": 0.25,
                "long_exposure": 0.25,
                "short_exposure": 0.0,
                "gross_factor_exposure": 0.5,
                "gross_normalized_exposure": 0.25,
            }
        ],
        "dataset_fingerprint": "dataset-fp",
        "dataset_identity": ["dataset", "1"],
        "signal_construction": "WEIGHTED_NORMALIZED_RANK_AVERAGE",
    }


def test_assess_research_portfolio_factor_risk_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/portfolios/factor-risk",
            json=payload(),
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal
    assert response.status_code == 401
