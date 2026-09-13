from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.api.dependencies import (
    get_research_dataset_service,
    get_research_factor_computation_service,
)
from quantcore.services.research_factor_computation_service import ResearchFactorValue


client = TestClient(app)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_factor_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def test_get_research_factor_returns_stable_pit_contract():
    feature_service = Mock()
    feature_service.build_feature_vector.return_value = Mock(
        symbol="AAPL",
        security_id=42,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
    )

    factor_service = Mock()
    factor_service.compute_factor.return_value = ResearchFactorValue(
        factor_key="quality_score",
        definition_version="1",
        symbol="AAPL",
        security_id=42,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        value_numeric=0.73,
        value_text=None,
        unit="score",
        input_manifest={"factor": {"factor_key": "quality_score"}},
    )

    app.dependency_overrides[get_research_dataset_service] = lambda: feature_service
    app.dependency_overrides[
        get_research_factor_computation_service
    ] = lambda: factor_service
    try:
        response = client.get(
            "/api/v1/research/factors/aapl",
            params={
                "factor_key": "quality_score",
                "definition_version": "1",
                "as_of": "2026-08-20T15:30:00Z",
            },
        )
    finally:
        app.dependency_overrides.pop(get_research_dataset_service, None)
        app.dependency_overrides.pop(get_research_factor_computation_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "factor_key": "quality_score",
        "definition_version": "1",
        "symbol": "AAPL",
        "security_id": 42,
        "as_of": "2026-08-20T15:30:00Z",
        "value_numeric": 0.73,
        "value_text": None,
        "unit": "score",
        "input_manifest": {"factor": {"factor_key": "quality_score"}},
    }
    feature_service.build_feature_vector.assert_called_once_with(
        "aapl",
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
    )
    factor_service.compute_factor.assert_called_once_with(
        feature_service.build_feature_vector.return_value,
        factor_key="quality_score",
        definition_version="1",
    )


def test_research_factor_requires_as_of():
    response = client.get(
        "/api/v1/research/factors/AAPL",
        params={"factor_key": "quality_score", "definition_version": "1"},
    )
    assert response.status_code == 422


def test_research_factor_requires_factor_identity():
    response = client.get(
        "/api/v1/research/factors/AAPL",
        params={"as_of": "2026-08-20T15:30:00Z"},
    )
    assert response.status_code == 422


def test_research_factor_routes_reject_principal_without_scope():
    def unauthorized_principal() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            subject="test-user",
            issuer="https://issuer.example",
            claims={"sub": "test-user"},
        )

    app.dependency_overrides[get_current_principal] = unauthorized_principal
    try:
        response = client.get(
            "/api/v1/research/factors/AAPL",
            params={
                "factor_key": "quality_score",
                "definition_version": "1",
                "as_of": "2026-08-20T15:30:00Z",
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_research_factor_routes_require_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.get(
            "/api/v1/research/factors/AAPL",
            params={
                "factor_key": "quality_score",
                "definition_version": "1",
                "as_of": "2026-08-20T15:30:00Z",
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_research_factor_route_is_in_openapi():
    assert "/api/v1/research/factors/{symbol}" in app.openapi()["paths"]
