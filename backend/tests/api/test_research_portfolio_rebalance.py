from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductResult,
    ResearchPortfolioRebalanceProductResult,
)
from quantcore.services.research_rebalance_service import (
    ResearchRebalanceActionType,
    ResearchRebalanceFrequency,
    ResearchRebalanceStatus,
)

client = TestClient(app)
CURRENT_AS_OF = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
TARGET_AS_OF = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_portfolio_rebalance_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def payload():
    return {
        "symbols": ["AAA", "BBB"],
        "as_ofs": [CURRENT_AS_OF.isoformat(), TARGET_AS_OF.isoformat()],
        "current_as_of": CURRENT_AS_OF.isoformat(),
        "target_as_of": TARGET_AS_OF.isoformat(),
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
        "rebalance_key": "monthly",
        "rebalance_definition_version": "1",
        "frequency": "MONTHLY",
    }


def test_rebalance_research_portfolio_returns_stable_contract():
    action = Mock(
        symbol="AAA",
        security_id=1,
        current_weight=0.5,
        target_weight=1.0,
        weight_delta=0.5,
        action=ResearchRebalanceActionType.INCREASE,
    )
    rebalance = Mock(
        rebalance_key="monthly",
        rebalance_definition_version="1",
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        frequency=ResearchRebalanceFrequency.MONTHLY,
        current_as_of=CURRENT_AS_OF,
        as_of=TARGET_AS_OF,
        current_gross_exposure=0.5,
        current_net_exposure=0.5,
        target_gross_exposure=1.0,
        target_net_exposure=1.0,
        turnover=0.25,
        status=ResearchRebalanceStatus.REBALANCED,
        actions=(action,),
    )
    result = ResearchPortfolioRebalanceProductResult(
        current=ResearchPortfolioProductResult(
            portfolio=Mock(),
            dataset_fingerprint="current-fp",
            dataset_identity=("dataset", "1"),
            signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
        ),
        target=ResearchPortfolioProductResult(
            portfolio=Mock(),
            dataset_fingerprint="target-fp",
            dataset_identity=("dataset", "1"),
            signal_construction="WEIGHTED_NORMALIZED_RANK_AVERAGE",
        ),
        rebalance=rebalance,
    )
    product_service = Mock()
    product_service.construct_with_rebalance.return_value = result

    with patch(
        "quantcore.api.dependencies.ResearchPortfolioProductService",
        return_value=product_service,
    ):
        response = client.post(
            "/api/v1/research/portfolios/rebalance",
            json=payload(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "rebalance_key": "monthly",
        "rebalance_definition_version": "1",
        "strategy_key": "quality_long",
        "strategy_definition_version": "1",
        "signal_identity": ["quality_signal", "1"],
        "frequency": "MONTHLY",
        "current_as_of": "2026-08-20T15:30:00Z",
        "as_of": "2026-08-21T15:30:00Z",
        "current_dataset_fingerprint": "current-fp",
        "current_dataset_identity": ["dataset", "1"],
        "target_dataset_fingerprint": "target-fp",
        "target_dataset_identity": ["dataset", "1"],
        "signal_construction": "WEIGHTED_NORMALIZED_RANK_AVERAGE",
        "current_gross_exposure": 0.5,
        "current_net_exposure": 0.5,
        "target_gross_exposure": 1.0,
        "target_net_exposure": 1.0,
        "turnover": 0.25,
        "status": "REBALANCED",
        "actions": [
            {
                "symbol": "AAA",
                "security_id": 1,
                "current_weight": 0.5,
                "target_weight": 1.0,
                "weight_delta": 0.5,
                "action": "INCREASE",
            }
        ],
    }
    product_service.construct_with_rebalance.assert_called_once()


def test_rebalance_research_portfolio_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/portfolios/rebalance",
            json=payload(),
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal
    assert response.status_code == 401


def test_rebalance_research_portfolio_bounds_request_size():
    body = payload()
    body["symbols"] = [f"S{i}" for i in range(101)]
    response = client.post(
        "/api/v1/research/portfolios/rebalance",
        json=body,
    )
    assert response.status_code in {400, 422}
