from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_research_experiment_service
from quantcore.models.research_experiment import ResearchExperimentRunStatus
from quantcore.schemas.research_experiments import (
    ResearchExperimentArtifactProvenanceResponse,
    ResearchExperimentArtifactResponse,
    ResearchExperimentComparisonResultResponse,
    ResearchExperimentRunResponse,
    ResearchExperimentRunResultResponse,
)
from quantcore.services.research_experiment_service import (
    ResearchExperimentRunQuery,
    ResearchExperimentService,
)


router = APIRouter(
    prefix="/api/v1/research/experiments",
    tags=["Research Experiments"],
)


def _to_run_response(view) -> ResearchExperimentRunResponse:
    return ResearchExperimentRunResponse(
        run_id=view.run_id,
        experiment_key=view.experiment_key,
        definition_version=view.definition_version,
        run_input_fingerprint=view.run_input_fingerprint,
        dataset_fingerprint=view.dataset_fingerprint,
        execution_input_fingerprint=view.execution_input_fingerprint,
        definition_payload=view.definition_payload,
        status=view.status,
        submitted_at=view.submitted_at,
        started_at=view.started_at,
        finished_at=view.finished_at,
        error_summary=view.error_summary,
    )


def _to_result_response(view) -> ResearchExperimentRunResultResponse:
    return ResearchExperimentRunResultResponse(
        run_id=view.run_id,
        result_payload=view.result_payload,
        metrics=view.metrics,
        result_fingerprint=view.result_fingerprint,
        recorded_at=view.recorded_at,
    )


def _to_artifact_response(view) -> ResearchExperimentArtifactResponse:
    return ResearchExperimentArtifactResponse(
        artifact_id=view.artifact_id,
        run_id=view.run_id,
        artifact_type=view.artifact_type,
        content_hash=view.content_hash,
        artifact_fingerprint=view.artifact_fingerprint,
        metadata=view.metadata,
        declared_provenance=view.provenance,
        created_at=view.created_at,
    )


def _to_provenance_response(view) -> ResearchExperimentArtifactProvenanceResponse:
    return ResearchExperimentArtifactProvenanceResponse(
        artifact_id=view.artifact_id,
        artifact_type=view.artifact_type,
        content_hash=view.content_hash,
        artifact_fingerprint=view.artifact_fingerprint,
        run_id=view.run_id,
        definition_payload=view.definition.canonical_payload,
        result_fingerprint=view.result_fingerprint,
        dataset_fingerprint=view.dataset_fingerprint,
        execution_input_fingerprint=view.execution_input_fingerprint,
    )


def _to_comparison_result_response(view) -> ResearchExperimentComparisonResultResponse:
    return ResearchExperimentComparisonResultResponse(
        comparison_fingerprint=view.comparison_fingerprint,
        selection_fingerprint=view.selection_fingerprint,
        experiment_key=view.experiment_key,
        definition_version=view.definition_version,
        comparison_payload=view.comparison_payload,
        result_payload=view.result_payload,
        result_fingerprint=view.result_fingerprint,
        recorded_at=view.recorded_at,
    )


@router.get(
    "/runs",
    response_model=list[ResearchExperimentRunResponse],
)
def list_research_experiment_runs(
    experiment_key: str | None = Query(default=None),
    definition_version: str | None = Query(default=None),
    status: list[ResearchExperimentRunStatus] | None = Query(default=None),
    submitted_after: datetime | None = Query(default=None),
    submitted_before: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    service: ResearchExperimentService = Depends(get_research_experiment_service),
):
    query = ResearchExperimentRunQuery(
        experiment_key=experiment_key,
        definition_version=definition_version,
        statuses=tuple(status) if status else None,
        submitted_after=submitted_after,
        submitted_before=submitted_before,
        limit=limit,
    )
    return [_to_run_response(view) for view in service.list_runs(query)]


@router.get(
    "/runs/{run_id}",
    response_model=ResearchExperimentRunResponse,
)
def get_research_experiment_run(
    run_id: str,
    service: ResearchExperimentService = Depends(get_research_experiment_service),
):
    return _to_run_response(service.get_run(run_id))


@router.get(
    "/runs/{run_id}/result",
    response_model=ResearchExperimentRunResultResponse,
)
def get_research_experiment_result(
    run_id: str,
    service: ResearchExperimentService = Depends(get_research_experiment_service),
):
    return _to_result_response(service.get_result(run_id))


@router.get(
    "/runs/{run_id}/artifacts",
    response_model=list[ResearchExperimentArtifactResponse],
)
def list_research_experiment_artifacts(
    run_id: str,
    service: ResearchExperimentService = Depends(get_research_experiment_service),
):
    return [_to_artifact_response(view) for view in service.list_artifacts(run_id)]


@router.get(
    "/artifacts/{artifact_id}",
    response_model=ResearchExperimentArtifactResponse,
)
def get_research_experiment_artifact(
    artifact_id: str,
    service: ResearchExperimentService = Depends(get_research_experiment_service),
):
    return _to_artifact_response(service.get_artifact(artifact_id))


@router.get(
    "/artifacts/{artifact_id}/provenance",
    response_model=ResearchExperimentArtifactProvenanceResponse,
)
def get_research_experiment_artifact_provenance(
    artifact_id: str,
    service: ResearchExperimentService = Depends(get_research_experiment_service),
):
    return _to_provenance_response(service.get_artifact_provenance(artifact_id))


@router.get(
    "/comparison-results/{result_fingerprint}",
    response_model=ResearchExperimentComparisonResultResponse,
)
def get_research_experiment_comparison_result(
    result_fingerprint: str,
    service: ResearchExperimentService = Depends(get_research_experiment_service),
):
    return _to_comparison_result_response(
        service.get_comparison_result(result_fingerprint)
    )
