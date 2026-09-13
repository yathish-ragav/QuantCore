from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.services.research_factor_evaluation_service import (
    ResearchFactorEvaluation,
    ResearchFactorEvaluationSlice,
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
def _authenticated_research_factor_evaluation_api():
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


def make_evaluation():
    return ResearchFactorEvaluation(
        factor_key="quality_score",
        definition_version="1",
        cross_section_count=1,
        total_observation_count=2,
        minimum_cross_section_size=2,
        maximum_cross_section_size=2,
        mean_cross_section_size=2.0,
        mean_cross_section_value=0.35,
        mean_cross_section_stddev=0.15,
        mean_cross_section_range=0.3,
        cross_sections=(
            ResearchFactorEvaluationSlice(
                as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
                observation_count=2,
                mean_value=0.35,
                median_value=0.35,
                stddev_value=0.15,
                minimum_value=0.2,
                maximum_value=0.5,
                range_value=0.3,
            ),
        ),
    )


def test_evaluate_research_factor_returns_stable_contract():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as historical_factory, patch(
        "quantcore.api.dependencies.ResearchFactorPanelService"
    ) as panel_factory, patch(
        "quantcore.api.dependencies.ResearchFactorCrossSectionalService"
    ) as cross_sectional_factory, patch(
        "quantcore.api.dependencies.ResearchFactorEvaluationService"
    ) as evaluation_factory:
        historical_service = Mock()
        historical_service.build_historical_dataset.return_value = make_dataset()
        historical_factory.return_value = historical_service

        panel_service = Mock()
        panel_service.build_factor_panel.return_value = Mock()
        panel_factory.return_value = panel_service

        cross_sectional_service = Mock()
        ranked_panel = Mock()
        cross_sectional_service.rank_factor_panel.return_value = ranked_panel
        cross_sectional_factory.return_value = cross_sectional_service

        evaluation_service = Mock()
        evaluation_service.evaluate_ranked_panel.return_value = make_evaluation()
        evaluation_factory.return_value = evaluation_service

        response = client.post(
            "/api/v1/research/factors/evaluation",
            json={
                "symbols": ["aapl"],
                "as_ofs": ["2026-08-20T15:30:00Z"],
                "definition_identities": [["roe", "1"]],
                "dataset_identity": ["quality-dataset", "1"],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
                "higher_is_better": False,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["factor_key"] == "quality_score"
    assert body["definition_version"] == "1"
    assert body["dataset_identity"] == ["quality-dataset", "1"]
    assert len(body["dataset_fingerprint"]) == 64
    assert body["cross_section_count"] == 1
    assert body["total_observation_count"] == 2
    assert body["mean_cross_section_value"] == pytest.approx(0.35)
    assert body["row_count"] == 1
    assert body["cross_sections"][0]["median_value"] == pytest.approx(0.35)
    assert body["cross_sections"][0]["range_value"] == pytest.approx(0.3)
    historical_service.build_historical_dataset.assert_called_once_with(
        ["aapl"],
        as_ofs=[datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)],
        definition_identities=[("roe", "1")],
        dataset_identity=("quality-dataset", "1"),
    )
    cross_sectional_service.rank_factor_panel.assert_called_once_with(
        panel_service.build_factor_panel.return_value,
        higher_is_better=False,
    )
    evaluation_service.evaluate_ranked_panel.assert_called_once_with(ranked_panel)


def test_research_factor_evaluation_rejects_oversized_request():
    with patch(
        "quantcore.api.dependencies.ResearchHistoricalAnalysisService"
    ) as historical_factory:
        historical_factory.return_value = Mock()
        response = client.post(
            "/api/v1/research/factors/evaluation",
            json={
                "symbols": [f"SYM{i}" for i in range(100)],
                "as_ofs": [
                    f"2026-08-{day:02d}T15:30:00Z" for day in range(1, 12)
                ],
                "factor_key": "quality_score",
                "factor_definition_version": "1",
            },
        )

    assert response.status_code == 400
    historical_factory.return_value.build_historical_dataset.assert_not_called()


def test_research_factor_evaluation_requires_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.post(
            "/api/v1/research/factors/evaluation",
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


def test_research_factor_evaluation_requires_factor_identity():
    response = client.post(
        "/api/v1/research/factors/evaluation",
        json={
            "symbols": ["AAPL"],
            "as_ofs": ["2026-08-20T15:30:00Z"],
        },
    )
    assert response.status_code == 422
