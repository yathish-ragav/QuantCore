from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_strategy_service import ResearchStrategyDirection


client = TestClient(app)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_strategy_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def test_validate_research_strategy_returns_canonical_contract():
    strategy_service = Mock()
    with patch(
        "quantcore.api.dependencies.ResearchStrategyService",
        return_value=strategy_service,
    ):
        from quantcore.services.research_strategy_service import ResearchStrategyDefinition

        definition = ResearchStrategyDefinition(
            strategy_key="quality_long",
            definition_version="1",
            signal_identity=("quality_signal", "1"),
            direction=ResearchStrategyDirection.LONG_ONLY,
            long_threshold=0.8,
            description="Quality strategy",
        )
        strategy_service.validate_definition.return_value = definition

        response = client.post(
            "/api/v1/research/strategies",
            json={
                "strategy_key": "  quality_long  ",
                "definition_version": " 1 ",
                "signal_identity": ["quality_signal", "1"],
                "direction": "LONG_ONLY",
                "long_threshold": 0.8,
                "description": "  Quality strategy  ",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "strategy_key": "quality_long",
        "definition_version": "1",
        "signal_identity": ["quality_signal", "1"],
        "direction": "LONG_ONLY",
        "long_threshold": pytest.approx(0.8),
        "short_threshold": None,
        "description": "Quality strategy",
    }
    strategy_service.validate_definition.assert_called_once_with(definition)


def test_validate_research_strategy_rejects_invalid_long_only_threshold_contract():
    response = client.post(
        "/api/v1/research/strategies",
        json={
            "strategy_key": "quality_long",
            "definition_version": "1",
            "signal_identity": ["quality_signal", "1"],
            "direction": "LONG_ONLY",
        },
    )
    assert response.status_code == 400


def test_validate_research_strategy_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/strategies",
            json={
                "strategy_key": "quality_long",
                "definition_version": "1",
                "signal_identity": ["quality_signal", "1"],
                "direction": "LONG_ONLY",
                "long_threshold": 0.8,
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 401


def test_validate_research_strategy_rejects_invalid_direction_at_api_boundary():
    response = client.post(
        "/api/v1/research/strategies",
        json={
            "strategy_key": "quality_long",
            "definition_version": "1",
            "signal_identity": ["quality_signal", "1"],
            "direction": "INVALID",
            "long_threshold": 0.8,
        },
    )
    assert response.status_code == 422
