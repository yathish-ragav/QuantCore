from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintStatus,
)
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioConstraintProductResult,
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
def _authenticated_research_portfolio_constraints_api():
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
        "constraint_key": "retail_guardrails",
        "constraint_definition_version": "1",
        "max_position_weight": 0.25,
        "max_gross_exposure": 1.0,
        "max_net_exposure": 1.0,
    }


def test_validate_research_portfolio_constraints_returns_stable_contract():
    violation = Mock(
        constraint="max_position_weight",
        observed_value=0.30,
        limit=0.25,
    )
    snapshot = Mock(
        constraint_key="retail_guardrails",
        constraint_definition_version="1",
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=AS_OF,
        status=ResearchPortfolioConstraintStatus.VIOLATED,
        violations=(violation,),
        observed_max_position_weight=0.30,
        observed_gross_exposure=1.0,
        observed_net_exposure=1.0,
        observed_long_exposure=1.0,
        observed_short_exposure=0.0,
    )
    result = ResearchPortfolioConstraintProductResult(
        portfolio=Mock(
            dataset_fingerprint="dataset-fp",
            dataset_identity=("dataset", "1"),
            signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
        ),
        constraint=snapshot,
    )
    product_service = Mock()
    product_service.construct_with_constraints.return_value = result

    with patch(
        "quantcore.api.dependencies.ResearchPortfolioProductService",
        return_value=product_service,
    ):
        response = client.post(
            "/api/v1/research/portfolios/constraints",
            json=payload(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "constraint_key": "retail_guardrails",
        "constraint_definition_version": "1",
        "strategy_key": "quality_long",
        "strategy_definition_version": "1",
        "signal_identity": ["quality_signal", "1"],
        "as_of": "2026-08-20T15:30:00Z",
        "dataset_fingerprint": "dataset-fp",
        "dataset_identity": ["dataset", "1"],
        "signal_construction": "WEIGHTED_NORMALIZED_RANK_AVERAGE",
        "status": "VIOLATED",
        "violations": [
            {
                "constraint": "max_position_weight",
                "observed_value": 0.30,
                "limit": 0.25,
            }
        ],
        "observed_max_position_weight": 0.30,
        "observed_gross_exposure": 1.0,
        "observed_net_exposure": 1.0,
        "observed_long_exposure": 1.0,
        "observed_short_exposure": 0.0,
    }

    product_service.construct_with_constraints.assert_called_once()


def test_validate_research_portfolio_constraints_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/portfolios/constraints",
            json=payload(),
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal
    assert response.status_code == 401


def test_validate_research_portfolio_constraints_bounds_request_size():
    body = payload()
    body["symbols"] = [f"S{i}" for i in range(101)]
    response = client.post(
        "/api/v1/research/portfolios/constraints",
        json=body,
    )
    assert response.status_code == 422 or response.status_code == 400
