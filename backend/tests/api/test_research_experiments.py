from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from fastapi.testclient import TestClient

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.api.main import app
from quantcore.models.research_experiment import ResearchExperimentRunStatus


client = TestClient(app)


def authenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims={"sub": "test-user"},
    )


@pytest.fixture(autouse=True)
def _authenticated_research_api():
    app.dependency_overrides[get_current_principal] = authenticated_principal
    yield
    app.dependency_overrides.pop(get_current_principal, None)


def make_run(*, status=ResearchExperimentRunStatus.COMPLETED):
    view = Mock()
    view.run_id = "run-001"
    view.experiment_key = "value-quality"
    view.definition_version = "1"
    view.run_input_fingerprint = "a" * 64
    view.dataset_fingerprint = "b" * 64
    view.execution_input_fingerprint = "c" * 64
    view.definition_payload = {"experiment_key": "value-quality", "definition_version": "1"}
    view.status = status
    view.submitted_at = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    view.started_at = datetime(2026, 8, 20, 15, 31, tzinfo=timezone.utc)
    view.finished_at = datetime(2026, 8, 20, 15, 32, tzinfo=timezone.utc)
    view.error_summary = None
    return view


def make_result():
    view = Mock()
    view.run_id = "run-001"
    view.result_payload = {"sharpe": 1.2}
    view.metrics = {"sharpe": 1.2}
    view.result_fingerprint = "d" * 64
    view.recorded_at = datetime(2026, 8, 20, 15, 33, tzinfo=timezone.utc)
    return view


def make_artifact():
    view = Mock()
    view.artifact_id = "artifact-001"
    view.run_id = "run-001"
    view.artifact_type = "report"
    view.content_hash = "e" * 64
    view.artifact_fingerprint = "f" * 64
    view.metadata = {"format": "json"}
    view.provenance = {"declared_by": "executor"}
    view.created_at = datetime(2026, 8, 20, 15, 34, tzinfo=timezone.utc)
    return view


def make_provenance():
    view = Mock()
    view.artifact_id = "artifact-001"
    view.artifact_type = "report"
    view.content_hash = "e" * 64
    view.artifact_fingerprint = "f" * 64
    view.run_id = "run-001"
    view.definition.canonical_payload = {
        "experiment": {"key": "value-quality", "definition_version": "1"}
    }
    view.result_fingerprint = "d" * 64
    view.dataset_fingerprint = "b" * 64
    view.execution_input_fingerprint = "c" * 64
    return view


def make_comparison_result():
    view = Mock()
    view.comparison_fingerprint = "1" * 64
    view.selection_fingerprint = "2" * 64
    view.experiment_key = "value-quality"
    view.definition_version = "1"
    view.comparison_payload = {"runs": ["run-001", "run-002"]}
    view.result_payload = {"metrics": {"sharpe": {"run-001": 1.2, "run-002": 1.0}}}
    view.result_fingerprint = "3" * 64
    view.recorded_at = datetime(2026, 8, 20, 15, 35, tzinfo=timezone.utc)
    return view


def test_list_runs_exposes_versioned_research_contract_and_filters():
    with patch("quantcore.api.dependencies.ResearchExperimentService") as factory:
        service = Mock()
        service.list_runs.return_value = [make_run()]
        factory.return_value = service

        response = client.get(
            "/api/v1/research/experiments/runs",
            params=[
                ("experiment_key", "value-quality"),
                ("definition_version", "1"),
                ("status", "COMPLETED"),
                ("limit", "10"),
            ],
        )

    assert response.status_code == 200
    assert response.json()[0]["run_id"] == "run-001"
    assert response.json()[0]["dataset_fingerprint"] == "b" * 64
    query = service.list_runs.call_args.args[0]
    assert query.experiment_key == "value-quality"
    assert query.definition_version == "1"
    assert query.statuses == (ResearchExperimentRunStatus.COMPLETED,)
    assert query.limit == 10


def test_list_runs_rejects_invalid_limit_at_api_boundary():
    with patch("quantcore.api.dependencies.ResearchExperimentService") as factory:
        factory.return_value = Mock()
        response = client.get(
            "/api/v1/research/experiments/runs",
            params={"limit": 101},
        )

    assert response.status_code == 422


def test_get_run_returns_stable_run_contract():
    with patch("quantcore.api.dependencies.ResearchExperimentService") as factory:
        service = Mock()
        service.get_run.return_value = make_run()
        factory.return_value = service

        response = client.get("/api/v1/research/experiments/runs/run-001")

    assert response.status_code == 200
    assert response.json()["execution_input_fingerprint"] == "c" * 64
    service.get_run.assert_called_once_with("run-001")


def test_get_result_returns_stable_result_contract():
    with patch("quantcore.api.dependencies.ResearchExperimentService") as factory:
        service = Mock()
        service.get_result.return_value = make_result()
        factory.return_value = service

        response = client.get("/api/v1/research/experiments/runs/run-001/result")

    assert response.status_code == 200
    assert response.json()["result_fingerprint"] == "d" * 64
    service.get_result.assert_called_once_with("run-001")


def test_list_artifacts_returns_declared_provenance_separately():
    with patch("quantcore.api.dependencies.ResearchExperimentService") as factory:
        service = Mock()
        service.list_artifacts.return_value = [make_artifact()]
        factory.return_value = service

        response = client.get("/api/v1/research/experiments/runs/run-001/artifacts")

    assert response.status_code == 200
    assert response.json()[0]["declared_provenance"] == {"declared_by": "executor"}
    service.list_artifacts.assert_called_once_with("run-001")


def test_get_artifact_provenance_exposes_authoritative_lineage():
    with patch("quantcore.api.dependencies.ResearchExperimentService") as factory:
        service = Mock()
        service.get_artifact_provenance.return_value = make_provenance()
        factory.return_value = service

        response = client.get(
            "/api/v1/research/experiments/artifacts/artifact-001/provenance"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["dataset_fingerprint"] == "b" * 64
    assert data["execution_input_fingerprint"] == "c" * 64
    assert data["result_fingerprint"] == "d" * 64


def test_get_comparison_result_returns_persisted_snapshot():
    with patch("quantcore.api.dependencies.ResearchExperimentService") as factory:
        service = Mock()
        service.get_comparison_result.return_value = make_comparison_result()
        factory.return_value = service

        response = client.get(
            "/api/v1/research/experiments/comparison-results/" + "3" * 64
        )

    assert response.status_code == 200
    assert response.json()["comparison_fingerprint"] == "1" * 64
    service.get_comparison_result.assert_called_once_with("3" * 64)


def test_research_experiment_routes_are_in_openapi():
    paths = app.openapi()["paths"]
    assert "/api/v1/research/experiments/runs" in paths
    assert "/api/v1/research/experiments/runs/{run_id}" in paths
    assert "/api/v1/research/experiments/runs/{run_id}/result" in paths
    assert "/api/v1/research/experiments/runs/{run_id}/artifacts" in paths
    assert "/api/v1/research/experiments/artifacts/{artifact_id}" in paths
    assert "/api/v1/research/experiments/artifacts/{artifact_id}/provenance" in paths
    assert "/api/v1/research/experiments/comparison-results/{result_fingerprint}" in paths


def test_research_experiment_routes_require_authentication():
    app.dependency_overrides.pop(get_current_principal, None)
    try:
        response = client.get("/api/v1/research/experiments/runs")
    finally:
        app.dependency_overrides[get_current_principal] = authenticated_principal

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
