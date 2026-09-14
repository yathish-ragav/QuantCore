from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductResult,
    ResearchPortfolioRebalanceProductResult,
    ResearchPortfolioTransactionCostProductResult,
)
from quantcore.services.research_rebalance_service import (
    ResearchRebalanceFrequency,
    ResearchRebalanceStatus,
)
from quantcore.services.research_transaction_cost_service import ResearchTransactionCostStatus

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
def _authenticated_research_portfolio_transaction_cost_api():
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
        "rebalance_key": "daily",
        "rebalance_definition_version": "1",
        "frequency": "DAILY",
        "cost_key": "proportional",
        "cost_definition_version": "1",
        "one_way_cost_bps": 10.0,
    }


def test_calculate_research_portfolio_transaction_cost_returns_stable_contract():
    rebalance = Mock(
        rebalance_key="daily",
        rebalance_definition_version="1",
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        frequency=ResearchRebalanceFrequency.DAILY,
        current_as_of=CURRENT_AS_OF,
        as_of=TARGET_AS_OF,
    )
    cost = Mock(
        cost_key="proportional",
        cost_definition_version="1",
        rebalance_key="daily",
        rebalance_definition_version="1",
        strategy_key="quality_long",
        strategy_definition_version="1",
        signal_identity=("quality_signal", "1"),
        as_of=TARGET_AS_OF,
        turnover=0.25,
        one_way_cost_bps=10.0,
        cost_fraction=0.00025,
        cost_bps=2.5,
        status=ResearchTransactionCostStatus.CALCULATED,
    )
    result = ResearchPortfolioTransactionCostProductResult(
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
        transaction_cost=cost,
    )
    product_service = Mock()
    product_service.construct_with_transaction_cost.return_value = result

    with patch(
        "quantcore.api.dependencies.ResearchPortfolioProductService",
        return_value=product_service,
    ):
        response = client.post(
            "/api/v1/research/portfolios/transaction-costs",
            json=payload(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "cost_key": "proportional",
        "cost_definition_version": "1",
        "rebalance_key": "daily",
        "rebalance_definition_version": "1",
        "strategy_key": "quality_long",
        "strategy_definition_version": "1",
        "signal_identity": ["quality_signal", "1"],
        "frequency": "DAILY",
        "current_as_of": "2026-08-20T15:30:00Z",
        "as_of": "2026-08-21T15:30:00Z",
        "current_dataset_fingerprint": "current-fp",
        "current_dataset_identity": ["dataset", "1"],
        "target_dataset_fingerprint": "target-fp",
        "target_dataset_identity": ["dataset", "1"],
        "signal_construction": "WEIGHTED_NORMALIZED_RANK_AVERAGE",
        "turnover": 0.25,
        "one_way_cost_bps": 10.0,
        "cost_fraction": 0.00025,
        "cost_bps": 2.5,
        "status": "CALCULATED",
    }
    product_service.construct_with_transaction_cost.assert_called_once()


def test_calculate_research_portfolio_transaction_cost_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/portfolios/transaction-costs",
            json=payload(),
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal
    assert response.status_code == 401


def test_calculate_research_portfolio_transaction_cost_bounds_request_size():
    body = payload()
    body["symbols"] = [f"S{i}" for i in range(101)]
    response = client.post(
        "/api/v1/research/portfolios/transaction-costs",
        json=body,
    )
    assert response.status_code in {400, 422}
