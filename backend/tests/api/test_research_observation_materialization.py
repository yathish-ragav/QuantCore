from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.dependencies import get_research_observation_definition_service
from quantcore.api.main import app
from quantcore.core.exceptions import InvalidInputError

client = TestClient(app)


def principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="writer",
        issuer="https://issuer.example",
        claims={"sub": "writer", "scope": "research:read research:write"},
    )


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_principal] = principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)
    app.dependency_overrides.pop(get_research_observation_definition_service, None)


def test_materialize_route_commits_atomic_batch():
    db = Mock()
    service = Mock()
    service.db = db
    observation = Mock(
        observation_key="net_margin",
        definition_version="1",
        as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        value_numeric=0.2,
        value_text=None,
        unit="ratio",
        input_manifest={"formula": "net_income / revenue"},
        input_fingerprint="fingerprint",
    )
    service.materialize_observations.return_value = (observation,)
    app.dependency_overrides[get_research_observation_definition_service] = (
        lambda: service
    )

    response = client.post(
        "/research-observations/materialize",
        json={
            "symbol": "aapl",
            "as_of": "2026-08-20T15:30:00Z",
            "definition_identities": [["net_margin", "1"]],
        },
    )

    assert response.status_code == 200
    assert response.json()["materialized_count"] == 1
    assert response.json()["observations"][0]["input_fingerprint"] == "fingerprint"
    service.materialize_observations.assert_called_once()
    db.commit.assert_called_once()


def test_materialize_route_rolls_back_on_failure():
    db = Mock()
    service = Mock()
    service.db = db
    service.materialize_observations.side_effect = InvalidInputError("bad input")
    app.dependency_overrides[get_research_observation_definition_service] = (
        lambda: service
    )

    response = client.post(
        "/research-observations/materialize",
        json={
            "symbol": "AAPL",
            "as_of": "2026-08-20T15:30:00Z",
        },
    )

    assert response.status_code == 400
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_materialize_route_requires_write_scope():
    def read_only_principal():
        return AuthenticatedPrincipal(
            subject="reader",
            issuer="https://issuer.example",
            claims={"sub": "reader", "scope": "research:read"},
        )

    app.dependency_overrides[get_current_principal] = read_only_principal
    try:
        response = client.post(
            "/research-observations/materialize",
            json={
                "symbol": "AAPL",
                "as_of": "2026-08-20T15:30:00Z",
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = principal

    assert response.status_code == 403
