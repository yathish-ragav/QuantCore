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
def _authenticated_research_observation_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def make_observation(
    *,
    observation_key="roe",
    definition_version="1",
    as_of=None,
    value_numeric=0.18,
    value_text=None,
    unit="ratio",
):
    observation = Mock()
    observation.observation_key = observation_key
    observation.definition_version = definition_version
    observation.as_of = as_of or datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    observation.value_numeric = value_numeric
    observation.value_text = value_text
    observation.unit = unit
    observation.input_manifest = {"source": "pit-snapshot"}
    observation.input_fingerprint = "a" * 64
    observation.created_at = datetime(2026, 8, 20, 15, 31, tzinfo=timezone.utc)
    return observation


def test_get_research_observations_returns_exact_pit_rows():
    with patch("quantcore.api.dependencies.ResearchObservationService") as mock_service:
        service = Mock()
        service.get_for_symbol_as_of.return_value = [make_observation()]
        mock_service.return_value = service

        response = client.get(
            "/research-observations/aapl",
            params={"as_of": "2026-08-20T15:30:00Z"},
        )

    assert response.status_code == 200
    assert response.json() == [
        {
            "symbol": "AAPL",
            "observation_key": "roe",
            "definition_version": "1",
            "as_of": "2026-08-20T15:30:00Z",
            "value_numeric": 0.18,
            "value_text": None,
            "unit": "ratio",
            "input_manifest": {"source": "pit-snapshot"},
            "input_fingerprint": "a" * 64,
            "created_at": "2026-08-20T15:31:00Z",
        }
    ]
    service.get_for_symbol_as_of.assert_called_once_with(
        "AAPL",
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
    )


def test_get_latest_research_observations_uses_latest_pit_read():
    with patch("quantcore.api.dependencies.ResearchObservationService") as mock_service:
        service = Mock()
        service.get_latest_for_symbol_as_of.return_value = [
            make_observation(as_of=datetime(2026, 8, 19, tzinfo=timezone.utc))
        ]
        mock_service.return_value = service

        response = client.get(
            "/research-observations/AAPL/latest",
            params={"as_of": "2026-08-20T15:30:00Z"},
        )

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "AAPL"
    service.get_latest_for_symbol_as_of.assert_called_once_with(
        "AAPL",
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
    )


def test_research_observation_routes_reject_authenticated_principal_without_scope():
    def unauthorized_principal() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            subject="test-user",
            issuer="https://issuer.example",
            claims={"sub": "test-user"},
        )

    app.dependency_overrides[get_current_principal] = unauthorized_principal
    try:
        response = client.get(
            "/research-observations/AAPL",
            params={"as_of": "2026-08-20T15:30:00Z"},
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_research_observation_read_requires_as_of():
    with patch("quantcore.api.dependencies.ResearchObservationService") as mock_service:
        mock_service.return_value = Mock()
        response = client.get("/research-observations/AAPL")

    assert response.status_code == 422


def test_research_observation_latest_read_requires_as_of():
    with patch("quantcore.api.dependencies.ResearchObservationService") as mock_service:
        mock_service.return_value = Mock()
        response = client.get("/research-observations/AAPL/latest")

    assert response.status_code == 422
