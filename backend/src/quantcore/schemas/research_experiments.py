from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from quantcore.models.research_experiment import ResearchExperimentRunStatus


class ResearchExperimentRunResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    run_id: str
    experiment_key: str
    definition_version: str
    run_input_fingerprint: str
    dataset_fingerprint: str | None = None
    execution_input_fingerprint: str | None = None
    definition_payload: dict[str, Any]
    status: ResearchExperimentRunStatus
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_summary: str | None = None


class ResearchExperimentRunResultResponse(BaseModel):
    run_id: str
    result_payload: dict[str, Any]
    metrics: dict[str, Any]
    result_fingerprint: str
    recorded_at: datetime


class ResearchExperimentArtifactResponse(BaseModel):
    artifact_id: str
    run_id: str
    artifact_type: str
    content_hash: str
    artifact_fingerprint: str
    metadata: dict[str, Any]
    declared_provenance: dict[str, Any]
    created_at: datetime


class ResearchExperimentArtifactProvenanceResponse(BaseModel):
    artifact_id: str
    artifact_type: str
    content_hash: str
    artifact_fingerprint: str
    run_id: str
    definition_payload: dict[str, Any]
    result_fingerprint: str | None = None
    dataset_fingerprint: str | None = None
    execution_input_fingerprint: str | None = None


class ResearchExperimentComparisonResultResponse(BaseModel):
    comparison_fingerprint: str
    selection_fingerprint: str
    experiment_key: str
    definition_version: str
    comparison_payload: dict[str, Any]
    result_payload: dict[str, Any]
    result_fingerprint: str
    recorded_at: datetime
