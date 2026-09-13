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
def _authenticated_research_dataset_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def make_dataset():
    feature = Mock()
    feature.observation_key = "roe"
    feature.definition_version = "1"
    feature.observation_as_of = datetime(
        2026, 8, 20, 15, 30, tzinfo=timezone.utc
    )
    feature.value_numeric = 0.18
    feature.value_text = None
    feature.unit = "ratio"
    feature.input_manifest = {"source": "pit-snapshot"}
    feature.input_fingerprint = "a" * 64

    vector = Mock()
    vector.symbol = "AAPL"
    vector.security_id = 42
    vector.as_of = datetime(
        2026, 8, 20, 15, 30, tzinfo=timezone.utc
    )
    vector.input_fingerprint = "b" * 64
    vector.features = (feature,)

    row = Mock()
    row.symbol = "AAPL"
    row.security_id = 42
    row.as_of = vector.as_of
    row.feature_vector = vector

    dataset = Mock()
    dataset.dataset_fingerprint = "c" * 64
    dataset.definition_identities = (("roe", "1"),)
    dataset.dataset_identity = ("quality-dataset", "1")
    dataset.rows = (row,)
    return dataset


def test_build_research_historical_dataset_returns_stable_contract():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as factory:
        service = Mock()
        service.build_historical_dataset.return_value = make_dataset()
        factory.return_value = service

        response = client.post(
            "/api/v1/research/datasets/historical",
            json={
                "symbols": ["aapl"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "definition_identities": [["roe", "1"]],
                "dataset_identity": ["quality-dataset", "1"],
            },
        )

    assert response.status_code == 200
    assert response.json()["dataset_fingerprint"] == "c" * 64
    assert response.json()["definition_identities"] == [["roe", "1"]]
    assert response.json()["dataset_identity"] == ["quality-dataset", "1"]
    assert response.json()["row_count"] == 1
    assert response.json()["rows"][0]["feature_vector"]["input_fingerprint"] == (
        "b" * 64
    )
    service.build_historical_dataset.assert_called_once_with(
        ["aapl"],
        as_ofs=[
            datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
        ],
        definition_identities=[("roe", "1")],
        dataset_identity=("quality-dataset", "1"),
    )


def test_historical_dataset_rejects_oversized_row_request():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as factory:
        factory.return_value = Mock()
        response = client.post(
            "/api/v1/research/datasets/historical",
            json={
                "symbols": [f"SYM{i}" for i in range(100)],
                "as_ofs": [
                    f"2026-08-{day:02d}T15:30:00Z"
                    for day in range(1, 12)
                ],
            },
        )

    assert response.status_code == 400


def test_historical_dataset_requires_symbols():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as factory:
        factory.return_value = Mock()
        response = client.post(
            "/api/v1/research/datasets/historical",
            json={
                "symbols": [],
                "as_ofs": ["2026-08-20T15:30:00Z"],
            },
        )

    assert response.status_code == 422


def test_historical_dataset_requires_as_ofs():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as factory:
        factory.return_value = Mock()
        response = client.post(
            "/api/v1/research/datasets/historical",
            json={"symbols": ["AAPL"], "as_ofs": []},
        )

    assert response.status_code == 422


def test_research_dataset_routes_reject_principal_without_scope():
    def unauthorized_principal() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            subject="test-user",
            issuer="https://issuer.example",
            claims={"sub": "test-user"},
        )

    app.dependency_overrides[get_current_principal] = unauthorized_principal
    try:
        response = client.post(
            "/api/v1/research/datasets/historical",
            json={
                "symbols": ["AAPL"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_research_dataset_routes_require_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/datasets/historical",
            json={
                "symbols": ["AAPL"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_research_dataset_route_is_in_openapi():
    assert "/api/v1/research/datasets/historical" in app.openapi()["paths"]