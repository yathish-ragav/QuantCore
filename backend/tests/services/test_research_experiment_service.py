from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_experiment_service import (
    ResearchExperimentDefinition,
    ResearchExperimentDefinitionRegistry,
    ResearchExperimentArtifactDefinition,
    ResearchExperimentExecutionResult,
    ResearchExperimentRunResultView,
    ResearchExperimentRunStatus,
    ResearchExperimentRunView,
    ResearchExperimentService,
)


def definition(**overrides):
    values = {
        "experiment_key": "value-quality",
        "definition_version": "1",
        "dataset_identity": ("research-dataset", "1"),
        "universe_identity": ("us-equities", "1"),
        "observation_as_of": datetime(2026, 8, 1, 15, 30, tzinfo=timezone.utc),
        "factor_identities": (("value", "2"), ("quality", "1")),
        "signal_identity": ("value-quality-signal", "1"),
        "strategy_identity": ("long-short", "1"),
        "parameters": {"winsorize": {"lower": 0.01, "upper": 0.99}, "bucket_count": 5},
        "code_version": "abc123",
    }
    values.update(overrides)
    return ResearchExperimentDefinition(**values)


def test_definition_normalizes_and_exposes_identity():
    item = definition(experiment_key="  value-quality  ", definition_version=" 2 ")
    assert item.identity == ("value-quality", "2")
    assert item.dataset_identity == ("research-dataset", "1")
    assert item.parameters["bucket_count"] == 5


def test_as_of_must_be_timezone_aware():
    with pytest.raises(InvalidInputError, match="timezone-aware"):
        definition(observation_as_of=datetime(2026, 8, 1))


def test_as_of_must_not_be_future():
    with pytest.raises(InvalidInputError, match="future"):
        definition(observation_as_of=datetime.now(timezone.utc).replace(year=2099))


@pytest.mark.parametrize(
    "field,value",
    [
        ("dataset_identity", ("dataset", "")),
        ("universe_identity", ("", "1")),
        ("signal_identity", ("signal", "")),
        ("strategy_identity", ("strategy", "")),
    ],
)
def test_versioned_identities_must_be_complete(field, value):
    with pytest.raises(InvalidInputError):
        definition(**{field: value})


def test_factor_identities_reject_duplicates():
    with pytest.raises(InvalidInputError, match="duplicates"):
        definition(factor_identities=(("value", "1"), ("value", "1")))


def test_parameters_are_canonicalized():
    item = definition(parameters={"z": [2, {"b": 1, "a": 3}], "a": 1})
    assert list(item.parameters) == ["a", "z"]
    assert item.parameters["z"][1] == {"a": 3, "b": 1}


def test_parameters_are_immutable_after_definition_creation():
    item = definition(parameters={"nested": {"value": 1}, "items": [1, 2]})
    with pytest.raises(TypeError, match="Frozen"):
        item.parameters["nested"] = {}
    with pytest.raises(TypeError, match="Frozen"):
        item.parameters["nested"]["value"] = 2
    with pytest.raises(TypeError, match="Frozen"):
        item.parameters["items"].append(3)


@pytest.mark.parametrize("parameters", [{"bad": float("nan")}, {"bad": float("inf")}])
def test_parameters_reject_nonfinite_numbers(parameters):
    with pytest.raises(InvalidInputError, match="deterministic JSON"):
        definition(parameters=parameters)


def test_run_input_fingerprint_is_order_independent_for_mapping_parameters():
    first = definition(parameters={"a": 1, "b": {"x": 2, "y": 3}})
    second = definition(parameters={"b": {"y": 3, "x": 2}, "a": 1})
    assert first.run_input_fingerprint == second.run_input_fingerprint


def test_run_input_fingerprint_changes_when_definition_inputs_change():
    first = definition(parameters={"bucket_count": 5})
    second = definition(parameters={"bucket_count": 10})
    assert first.run_input_fingerprint != second.run_input_fingerprint


def test_registry_rejects_duplicate_identity():
    registry = ResearchExperimentDefinitionRegistry([definition()])
    with pytest.raises(InvalidInputError, match="already registered"):
        registry.register(definition())


def test_registry_resolves_definition():
    item = definition()
    registry = ResearchExperimentDefinitionRegistry([item])
    assert registry.get("value-quality", "1") is item


def test_registry_raises_for_missing_definition():
    registry = ResearchExperimentDefinitionRegistry()
    with pytest.raises(ResourceNotFoundError):
        registry.get("missing", "1")


def test_service_accepts_only_valid_definitions():
    item = definition()
    assert ResearchExperimentService.validate_definition(item) is item
    with pytest.raises(InvalidInputError):
        ResearchExperimentService.validate_definition(object())


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from quantcore.models.research_experiment import (
        ResearchExperimentRun,
        ResearchExperimentArtifact,
        ResearchExperimentRunResult,
    )

    engine = create_engine("sqlite://")
    ResearchExperimentRun.__table__.create(engine)
    ResearchExperimentRunResult.__table__.create(engine)
    ResearchExperimentArtifact.__table__.create(engine)
    with Session(engine) as session:
        yield session


def test_create_run_persists_identity_and_definition_snapshot(db_session):
    service = ResearchExperimentService(db_session)
    item = service.create_run(definition(), run_id="run-001")

    assert isinstance(item, ResearchExperimentRunView)
    assert item.run_id == "run-001"
    assert item.status.value == "QUEUED"
    assert item.run_input_fingerprint == definition().run_input_fingerprint
    assert item.definition_payload["experiment"]["key"] == "value-quality"

    persisted = service.get_run("run-001")
    assert persisted == item


def test_create_run_generates_unique_run_id(db_session):
    service = ResearchExperimentService(db_session)
    first = service.create_run(definition())
    second = service.create_run(definition())

    assert first.run_id != second.run_id
    assert first.run_input_fingerprint == second.run_input_fingerprint


def test_create_run_rejects_duplicate_explicit_run_id(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="duplicate")

    with pytest.raises(InvalidInputError, match="already exists"):
        service.create_run(definition(), run_id="duplicate")


def test_run_lifecycle_allows_queued_running_completed(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="lifecycle")

    running = service.start_run("lifecycle")
    assert running.status.value == "RUNNING"
    assert running.started_at is not None

    completed = service.complete_run("lifecycle")
    assert completed.status.value == "COMPLETED"
    assert completed.finished_at is not None


def test_run_failure_records_error_and_finishes(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="failure")
    service.start_run("failure")

    failed = service.fail_run("failure", error_summary="calculation failed")
    assert failed.status.value == "FAILED"
    assert failed.finished_at is not None
    assert failed.error_summary == "calculation failed"


def test_queued_run_can_be_cancelled(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="cancel")

    cancelled = service.cancel_run("cancel")
    assert cancelled.status.value == "CANCELLED"
    assert cancelled.finished_at is not None


def test_terminal_run_cannot_transition_again(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="terminal")
    service.cancel_run("terminal")

    with pytest.raises(InvalidInputError, match="cannot transition"):
        service.start_run("terminal")


def test_missing_run_is_not_found(db_session):
    service = ResearchExperimentService(db_session)
    with pytest.raises(ResourceNotFoundError, match="Experiment run not found"):
        service.get_run("missing")


def test_execution_result_is_canonical_and_fingerprinted():
    first = ResearchExperimentExecutionResult(
        result_payload={"b": {"y": 2, "x": 1}, "a": 3},
        metrics={"sharpe": 1.2, "count": 10},
    )
    second = ResearchExperimentExecutionResult(
        result_payload={"a": 3, "b": {"x": 1, "y": 2}},
        metrics={"count": 10, "sharpe": 1.2},
    )
    assert first.result_payload["b"]["x"] == 1
    assert first.result_fingerprint == second.result_fingerprint


def test_execution_result_rejects_nondeterministic_values():
    with pytest.raises(InvalidInputError, match="deterministic JSON"):
        ResearchExperimentExecutionResult(
            result_payload={"bad": float("nan")},
        )


def test_execute_run_persists_result_and_completes_run(db_session):
    service = ResearchExperimentService(db_session)
    item = service.create_run(definition(), run_id="execute-001")

    calls = []

    def executor(experiment_definition):
        calls.append(experiment_definition.identity)
        return ResearchExperimentExecutionResult(
            result_payload={"observations": 100, "status": "ok"},
            metrics={"sharpe": 1.25, "return": 0.18},
        )

    result = service.execute_run("execute-001", definition(), executor)

    assert isinstance(result, ResearchExperimentRunResultView)
    assert result.run_id == item.run_id
    assert result.result_payload["observations"] == 100
    assert result.metrics["sharpe"] == 1.25
    assert result.result_fingerprint
    assert calls == [definition().identity]
    assert service.get_run("execute-001").status is ResearchExperimentRunStatus.COMPLETED


def test_execute_run_rejects_definition_mismatch(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="execute-mismatch")

    with pytest.raises(InvalidInputError, match="does not match"):
        service.execute_run(
            "execute-mismatch",
            definition(parameters={"bucket_count": 10}),
            lambda _: ResearchExperimentExecutionResult(result_payload={}),
        )

    assert service.get_run("execute-mismatch").status is ResearchExperimentRunStatus.QUEUED


def test_execute_run_requires_typed_result(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="execute-invalid")

    with pytest.raises(InvalidInputError, match="must return ResearchExperimentExecutionResult"):
        service.execute_run("execute-invalid", definition(), lambda _: {"ok": True})

    run = service.get_run("execute-invalid")
    assert run.status is ResearchExperimentRunStatus.FAILED
    assert run.finished_at is not None
    with pytest.raises(ResourceNotFoundError, match="Experiment result not found"):
        service.get_result("execute-invalid")


def test_execute_run_records_executor_failure(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="execute-failure")

    def executor(_):
        raise RuntimeError("factor calculation failed")

    with pytest.raises(RuntimeError, match="factor calculation failed"):
        service.execute_run("execute-failure", definition(), executor)

    run = service.get_run("execute-failure")
    assert run.status is ResearchExperimentRunStatus.FAILED
    assert run.error_summary == "factor calculation failed"


def test_execute_run_rejects_nonqueued_run(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="execute-terminal")
    service.cancel_run("execute-terminal")

    with pytest.raises(InvalidInputError, match="not queued"):
        service.execute_run(
            "execute-terminal",
            definition(),
            lambda _: ResearchExperimentExecutionResult(result_payload={}),
        )


def test_get_result_requires_persisted_result(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="no-result")

    with pytest.raises(ResourceNotFoundError, match="Experiment result not found"):
        service.get_result("no-result")


def test_execute_run_result_is_reloaded_from_persistence(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="reload-result")

    service.execute_run(
        "reload-result",
        definition(),
        lambda _: ResearchExperimentExecutionResult(
            result_payload={"value": 42},
            metrics={"accuracy": 0.91},
        ),
    )

    reloaded = service.get_result("reload-result")
    assert reloaded.result_payload == {"value": 42}
    assert reloaded.metrics == {"accuracy": 0.91}


def test_artifact_definition_is_canonical_and_fingerprinted():
    first = ResearchExperimentArtifactDefinition(
        run_id="run-001",
        artifact_type="factor_panel",
        content_hash="A" * 64,
        metadata={"b": {"y": 2, "x": 1}, "a": 3},
        provenance={"source": "execution"},
    )
    second = ResearchExperimentArtifactDefinition(
        run_id="run-001",
        artifact_type="factor_panel",
        content_hash="a" * 64,
        metadata={"a": 3, "b": {"x": 1, "y": 2}},
        provenance={"source": "execution"},
    )
    assert first.metadata["b"]["x"] == 1
    assert first.content_hash == second.content_hash
    assert first.artifact_fingerprint == second.artifact_fingerprint


@pytest.mark.parametrize(
    "field,value",
    [
        ("artifact_type", ""),
        ("content_hash", "not-a-hash"),
        ("content_hash", "g" * 64),
    ],
)
def test_artifact_definition_validates_identity_fields(field, value):
    with pytest.raises(InvalidInputError):
        ResearchExperimentArtifactDefinition(
            run_id="run-001",
            artifact_type="factor_panel" if field != "artifact_type" else value,
            content_hash="a" * 64 if field != "content_hash" else value,
        )


def test_artifact_fingerprint_is_order_independent():
    first = ResearchExperimentArtifactDefinition(
        run_id="run-001", artifact_type="report", content_hash="a" * 64,
        metadata={"z": 2, "a": 1}, provenance={"b": 2, "a": 1},
    )
    second = ResearchExperimentArtifactDefinition(
        run_id="run-001", artifact_type="report", content_hash="a" * 64,
        metadata={"a": 1, "z": 2}, provenance={"a": 1, "b": 2},
    )
    assert first.artifact_fingerprint == second.artifact_fingerprint


def test_create_and_get_artifact_persists_provenance(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="artifact-run")
    artifact = service.create_artifact(
        ResearchExperimentArtifactDefinition(
            run_id="artifact-run",
            artifact_type="factor_panel",
            content_hash="a" * 64,
            metadata={"format": "json", "schema_version": 1},
            provenance={"producer": "research-experiment", "result": "run-result"},
        ),
        artifact_id="artifact-001",
    )

    assert artifact.artifact_id == "artifact-001"
    assert artifact.run_id == "artifact-run"
    assert artifact.content_hash == "a" * 64
    assert artifact.metadata["format"] == "json"
    assert artifact.provenance["result"] == "run-result"
    assert artifact.artifact_fingerprint
    assert service.get_artifact("artifact-001") == artifact


def test_get_artifact_validates_artifact_id():
    service = ResearchExperimentService.__new__(ResearchExperimentService)
    with pytest.raises(InvalidInputError, match="Experiment artifact id"):
        service.get_artifact("   ")


def test_artifact_requires_existing_run(db_session):
    service = ResearchExperimentService(db_session)
    with pytest.raises(ResourceNotFoundError, match="Experiment run not found"):
        service.create_artifact(
            ResearchExperimentArtifactDefinition(
                run_id="missing", artifact_type="report", content_hash="a" * 64
            )
        )


def test_artifact_registration_is_idempotency_protected(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="artifact-duplicate")
    artifact = ResearchExperimentArtifactDefinition(
        run_id="artifact-duplicate", artifact_type="report", content_hash="a" * 64
    )
    service.create_artifact(artifact)
    with pytest.raises(InvalidInputError, match="same identity"):
        service.create_artifact(artifact)


def test_artifacts_can_be_listed_by_run(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="artifact-list")
    service.create_artifact(
        ResearchExperimentArtifactDefinition(
            run_id="artifact-list", artifact_type="report", content_hash="a" * 64
        ),
        artifact_id="artifact-a",
    )
    service.create_artifact(
        ResearchExperimentArtifactDefinition(
            run_id="artifact-list", artifact_type="factor_panel", content_hash="b" * 64
        ),
        artifact_id="artifact-b",
    )

    artifacts = service.list_artifacts("artifact-list")
    assert [item.artifact_id for item in artifacts] == ["artifact-a", "artifact-b"]


def test_artifact_has_no_update_boundary(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="artifact-immutable")
    artifact = service.create_artifact(
        ResearchExperimentArtifactDefinition(
            run_id="artifact-immutable", artifact_type="report", content_hash="a" * 64
        ),
        artifact_id="artifact-immutable-1",
    )
    assert not hasattr(service, "update_artifact")
    assert artifact.artifact_id == "artifact-immutable-1"
