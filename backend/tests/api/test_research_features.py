from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app


client = TestClient(app)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_feature_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def make_vector():
    feature = Mock()
    feature.observation_key = "roe"
    feature.definition_version = "1"
    feature.observation_as_of = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    feature.value_numeric = 0.18
    feature.value_text = None
    feature.unit = "ratio"
    feature.input_manifest = {"source": "pit-snapshot"}
    feature.input_fingerprint = "a" * 64

    vector = Mock()
    vector.symbol = "AAPL"
    vector.security_id = 42
    vector.as_of = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    vector.input_fingerprint = "b" * 64
    vector.features = (feature,)
    return vector


def test_get_research_feature_vector_returns_stable_pit_contract():
    with patch("quantcore.api.dependencies.ResearchDatasetService") as factory:
        service = Mock()
        service.build_feature_vector.return_value = make_vector()
        factory.return_value = service

        response = client.get(
            "/api/v1/research/features/aapl",
            params={"as_of": "2026-08-20T15:30:00Z"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "AAPL",
        "security_id": 42,
        "as_of": "2026-08-20T15:30:00Z",
        "input_fingerprint": "b" * 64,
        "features": [
            {
                "observation_key": "roe",
                "definition_version": "1",
                "observation_as_of": "2026-08-20T15:30:00Z",
                "value_numeric": 0.18,
                "value_text": None,
                "unit": "ratio",
                "input_manifest": {"source": "pit-snapshot"},
                "input_fingerprint": "a" * 64,
            }
        ],
    }
    service.build_feature_vector.assert_called_once_with(
        "aapl",
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
    )


def test_research_feature_vector_requires_as_of():
    with patch("quantcore.api.dependencies.ResearchDatasetService") as factory:
        factory.return_value = Mock()
        response = client.get("/api/v1/research/features/AAPL")

    assert response.status_code == 422


def test_research_feature_routes_reject_principal_without_scope():
    def unauthorized_principal() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            subject="test-user",
            issuer="https://issuer.example",
            claims={"sub": "test-user"},
        )

    app.dependency_overrides[get_current_principal] = unauthorized_principal
    try:
        response = client.get(
            "/api/v1/research/features/AAPL",
            params={"as_of": "2026-08-20T15:30:00Z"},
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_research_feature_routes_require_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.get(
            "/api/v1/research/features/AAPL",
            params={"as_of": "2026-08-20T15:30:00Z"},
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_research_feature_route_is_in_openapi():
    assert "/api/v1/research/features/{symbol}" in app.openapi()["paths"]
