from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_panel_service import (
    ResearchFactorPanel,
    ResearchFactorPanelRow,
)
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalDataset,
    ResearchHistoricalDatasetRow,
)


client = TestClient(app)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user", "scope": "research:read"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_factor_panel_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def make_dataset():
    from quantcore.services.research_dataset_service import ResearchFeatureVector

    vector = ResearchFeatureVector(
        symbol="AAPL",
        security_id=42,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        features=(),
    )
    row = ResearchHistoricalDatasetRow(
        symbol="AAPL",
        security_id=42,
        as_of=vector.as_of,
        feature_vector=vector,
    )
    return ResearchHistoricalDataset(
        rows=(row,),
        definition_identities=(("roe", "1"),),
        dataset_identity=("quality-dataset", "1"),
    )


def make_panel():
    factor_value = ResearchFactorValue(
        factor_key="quality_score",
        definition_version="1",
        symbol="AAPL",
        security_id=42,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        value_numeric=0.25,
        unit="score",
        input_manifest={"source": "test"},
    )
    return ResearchFactorPanel(
        factor_key="quality_score",
        definition_version="1",
        rows=(
            ResearchFactorPanelRow(
                symbol="AAPL",
                security_id=42,
                as_of=factor_value.as_of,
                factor_value=factor_value,
            ),
        ),
        unit="score",
    )


def test_build_research_factor_panel_returns_stable_contract():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as historical_factory, patch(
        "quantcore.api.dependencies.get_research_factor_computation_service"
    ), patch(
        "quantcore.api.dependencies.ResearchFactorPanelService"
    ) as panel_factory:
        historical_service = Mock()
        historical_service.build_historical_dataset.return_value = make_dataset()
        historical_factory.return_value = historical_service

        panel_service = Mock()
        panel_service.build_factor_panel.return_value = make_panel()
        panel_factory.return_value = panel_service

        response = client.post(
            "/api/v1/research/factors/panel",
            json={
                "symbols": ["aapl"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "definition_identities": [["roe", "1"]],
                "dataset_identity": ["quality-dataset", "1"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["factor_key"] == "quality_score"
    assert body["definition_version"] == "1"
    assert body["dataset_identity"] == ["quality-dataset", "1"]
    assert len(body["dataset_fingerprint"]) == 64
    assert body["unit"] == "score"
    assert body["row_count"] == 1
    assert body["rows"][0]["value_numeric"] == 0.25
    assert body["rows"][0]["input_manifest"] == {"source": "test"}
    historical_service.build_historical_dataset.assert_called_once_with(
        ["aapl"],
        as_ofs=[datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)],
        definition_identities=[("roe", "1")],
        dataset_identity=("quality-dataset", "1"),
    )
    panel_service.build_factor_panel.assert_called_once()


def test_research_factor_panel_rejects_oversized_row_request():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as historical_factory:
        historical_factory.return_value = Mock()
        response = client.post(
            "/api/v1/research/factors/panel",
            json={
                "symbols": [f"SYM{i}" for i in range(100)],
                "as_ofs": [
                    f"2026-08-{day:02d}T15:30:00Z"
                    for day in range(1, 12)
                ],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
            },
        )

    assert response.status_code == 400


def test_research_factor_panel_requires_factor_identity():
    response = client.post(
        "/api/v1/research/factors/panel",
        json={
            "symbols": ["AAPL"],
            "as_ofs": ["2026-08-20T15:30:00Z"],
        },
    )
    assert response.status_code == 422


def test_research_factor_panel_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/factors/panel",
            json={
                "symbols": ["AAPL"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_research_factor_panel_rejects_principal_without_scope():
    def unauthorized_principal() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            subject="test-user",
            issuer="https://issuer.example",
            claims={"sub": "test-user"},
        )

    app.dependency_overrides[get_current_principal] = unauthorized_principal
    try:
        response = client.post(
            "/api/v1/research/factors/panel",
            json={
                "symbols": ["AAPL"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
            },
        )
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_research_factor_panel_route_is_in_openapi():
    assert "/api/v1/research/factors/panel" in app.openapi()["paths"]
