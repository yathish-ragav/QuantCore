from datetime import datetime, timedelta, timezone
import json

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_experiment_service import (
    ResearchExperimentDefinition,
    ResearchExperimentDefinitionRegistry,
    ResearchExperimentArtifactDefinition,
    ResearchExperimentArtifactProvenance,
    ResearchExperimentExecutionResult,
    ResearchExperimentComparison,
    ResearchExperimentComparisonRun,
    ResearchExperimentRunQuery,
    ResearchExperimentRunSelection,
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


def test_definition_can_be_reconstructed_from_canonical_payload():
    original = definition()
    reconstructed = ResearchExperimentDefinition.from_canonical_payload(
        original.canonical_payload
    )
    assert reconstructed.canonical_payload == original.canonical_payload
    assert reconstructed.run_input_fingerprint == original.run_input_fingerprint


def test_definition_reconstruction_rejects_invalid_snapshot():
    with pytest.raises(InvalidInputError, match="snapshot"):
        ResearchExperimentDefinition.from_canonical_payload(
            {"experiment": {"key": "value-quality"}}
        )


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


def test_run_query_returns_newest_runs_in_deterministic_order(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="query-001")
    service.create_run(definition(), run_id="query-002")
    service.create_run(definition(), run_id="query-003")

    runs = service.list_runs(ResearchExperimentRunQuery(limit=2))

    assert [item.run_id for item in runs] == ["query-003", "query-002"]


def test_run_query_filters_by_identity_status_and_submission_window(db_session):
    service = ResearchExperimentService(db_session)
    first = service.create_run(
        definition(experiment_key="momentum"), run_id="query-filter-001"
    )
    second = service.create_run(
        definition(experiment_key="value-quality", definition_version="2"),
        run_id="query-filter-002",
    )
    third = service.create_run(
        definition(experiment_key="value-quality", definition_version="2"),
        run_id="query-filter-003",
    )
    service.start_run(second.run_id)
    service.start_run(third.run_id)

    first_timestamp = datetime(2026, 9, 10, 13, 30, tzinfo=timezone.utc)
    second_timestamp = datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)
    third_timestamp = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)

    first_row = service.repository.get(first.run_id)
    second_row = service.repository.get(second.run_id)
    third_row = service.repository.get(third.run_id)
    first_row.submitted_at = first_timestamp
    second_row.submitted_at = second_timestamp
    third_row.submitted_at = third_timestamp
    db_session.commit()

    runs = service.list_runs(
        ResearchExperimentRunQuery(
            experiment_key=" value-quality ",
            definition_version="2",
            statuses=(ResearchExperimentRunStatus.RUNNING,),
            submitted_after=datetime(2026, 9, 10, 12, 59, tzinfo=timezone.utc),
            submitted_before=datetime(2026, 9, 10, 13, 1, tzinfo=timezone.utc),
        )
    )

    assert [item.run_id for item in runs] == [second.run_id]
    assert first.run_id not in {item.run_id for item in runs}
    assert third.run_id not in {item.run_id for item in runs}


def test_run_selection_is_order_independent_and_fingerprinted():
    first = ResearchExperimentRunSelection(
        run_ids=("run-003", "run-001", "run-002"),
        experiment_key=" value-quality ",
        definition_version=" 2 ",
    )
    second = ResearchExperimentRunSelection(
        run_ids=("run-002", "run-003", "run-001"),
        experiment_key="value-quality",
        definition_version="2",
    )

    assert first.run_ids == ("run-001", "run-002", "run-003")
    assert first.canonical_payload == second.canonical_payload
    assert first.selection_fingerprint == second.selection_fingerprint


def test_run_selection_rejects_empty_duplicates_and_oversized_sets():
    with pytest.raises(InvalidInputError, match="at least one"):
        ResearchExperimentRunSelection(run_ids=())

    with pytest.raises(InvalidInputError, match="must not contain duplicates"):
        ResearchExperimentRunSelection(run_ids=("run-001", "run-001"))

    with pytest.raises(InvalidInputError, match="between 1 and 100"):
        ResearchExperimentRunSelection(run_ids=("run-001",), max_runs=101)

    with pytest.raises(InvalidInputError, match="more than max_runs"):
        ResearchExperimentRunSelection(run_ids=("run-001", "run-002"), max_runs=1)


def test_run_selection_resolves_existing_runs_in_deterministic_order(db_session):
    service = ResearchExperimentService(db_session)
    first = service.create_run(definition(), run_id="selection-001")
    second = service.create_run(definition(), run_id="selection-002")
    third = service.create_run(definition(), run_id="selection-003")

    service.repository.get(first.run_id).submitted_at = datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)
    service.repository.get(second.run_id).submitted_at = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)
    service.repository.get(third.run_id).submitted_at = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
    db_session.commit()

    runs = service.select_runs(
        ResearchExperimentRunSelection(
            run_ids=(first.run_id, third.run_id, second.run_id),
        )
    )

    assert [item.run_id for item in runs] == [second.run_id, third.run_id, first.run_id]


def test_run_selection_rejects_missing_runs(db_session):
    service = ResearchExperimentService(db_session)
    with pytest.raises(ResourceNotFoundError, match="Experiment runs not found"):
        service.select_runs(
            ResearchExperimentRunSelection(run_ids=("missing-001", "missing-002"))
        )


def test_run_selection_enforces_optional_experiment_identity(db_session):
    service = ResearchExperimentService(db_session)
    matching = service.create_run(definition(), run_id="selection-match")
    service.create_run(definition(experiment_key="momentum"), run_id="selection-mismatch")

    selected = service.select_runs(
        ResearchExperimentRunSelection(
            run_ids=(matching.run_id,),
            experiment_key="value-quality",
            definition_version="1",
        )
    )
    assert [item.run_id for item in selected] == [matching.run_id]

    with pytest.raises(InvalidInputError, match="experiment key"):
        service.select_runs(
            ResearchExperimentRunSelection(
                run_ids=(matching.run_id, "selection-mismatch"),
                experiment_key="value-quality",
            )
        )

    with pytest.raises(InvalidInputError, match="definition version"):
        service.select_runs(
            ResearchExperimentRunSelection(
                run_ids=(matching.run_id,),
                definition_version="2",
            )
        )


def test_run_selection_rejects_wrong_selection_type(db_session):
    service = ResearchExperimentService(db_session)
    with pytest.raises(InvalidInputError, match="ResearchExperimentRunSelection"):
        service.select_runs(object())


def test_run_query_rejects_invalid_limit():
    with pytest.raises(InvalidInputError, match="between 1 and 100"):
        ResearchExperimentRunQuery(limit=0)

    with pytest.raises(InvalidInputError, match="between 1 and 100"):
        ResearchExperimentRunQuery(limit=101)


def test_run_query_rejects_invalid_filters():
    with pytest.raises(InvalidInputError, match="timezone-aware"):
        ResearchExperimentRunQuery(
            submitted_after=datetime(2026, 8, 1),
        )

    with pytest.raises(InvalidInputError, match="must not contain duplicates"):
        ResearchExperimentRunQuery(
            statuses=(
                ResearchExperimentRunStatus.QUEUED,
                ResearchExperimentRunStatus.QUEUED,
            )
        )

    with pytest.raises(InvalidInputError, match="later than"):
        ResearchExperimentRunQuery(
            submitted_after=datetime(2026, 8, 2, tzinfo=timezone.utc),
            submitted_before=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )


def test_run_query_rejects_wrong_query_type(db_session):
    service = ResearchExperimentService(db_session)
    with pytest.raises(InvalidInputError, match="ResearchExperimentRunQuery"):
        service.list_runs(object())


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


def test_artifact_fingerprint_excludes_caller_supplied_provenance():
    first = ResearchExperimentArtifactDefinition(
        run_id="artifact-identity",
        artifact_type="report",
        content_hash="a" * 64,
        metadata={"format": "json"},
        provenance={"producer": "caller-a"},
    )
    second = ResearchExperimentArtifactDefinition(
        run_id="artifact-identity",
        artifact_type="report",
        content_hash="a" * 64,
        metadata={"format": "json"},
        provenance={"producer": "caller-b", "claim": "untrusted"},
    )

    assert first.artifact_fingerprint == second.artifact_fingerprint
    assert first.provenance != second.provenance


def test_artifact_identity_payload_excludes_caller_supplied_provenance():
    artifact = ResearchExperimentArtifactDefinition(
        run_id="artifact-identity-payload",
        artifact_type="report",
        content_hash="b" * 64,
        provenance={"producer": "caller-asserted"},
    )

    assert "provenance" not in artifact.canonical_payload


def test_artifact_provenance_is_derived_from_persisted_run(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="artifact-provenance")
    artifact = service.create_artifact(
        ResearchExperimentArtifactDefinition(
            run_id="artifact-provenance",
            artifact_type="factor_panel",
            content_hash="a" * 64,
            provenance={
                "experiment_key": "caller-asserted-value",
                "dataset": "caller-asserted-dataset",
            },
        ),
        artifact_id="artifact-provenance-1",
    )

    provenance = service.get_artifact_provenance("artifact-provenance-1")

    assert isinstance(provenance, ResearchExperimentArtifactProvenance)
    assert provenance.run_id == "artifact-provenance"
    assert provenance.definition.identity == ("value-quality", "1")
    assert provenance.definition.dataset_identity == ("research-dataset", "1")
    assert provenance.definition.observation_as_of == definition().observation_as_of
    assert provenance.result_fingerprint is None
    assert "caller-asserted-value" not in json.dumps(provenance.canonical_payload)
    assert provenance.provenance_fingerprint


def test_artifact_provenance_includes_persisted_result_fingerprint(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="artifact-result-provenance")
    service.execute_run(
        "artifact-result-provenance",
        definition(),
        lambda _: ResearchExperimentExecutionResult(
            result_payload={"value": 42},
            metrics={"sharpe": 1.2},
        ),
    )
    artifact = service.create_artifact(
        ResearchExperimentArtifactDefinition(
            run_id="artifact-result-provenance",
            artifact_type="report",
            content_hash="b" * 64,
            provenance={"result_fingerprint": "caller-asserted"},
        ),
        artifact_id="artifact-result-provenance-1",
    )

    provenance = service.get_artifact_provenance("artifact-result-provenance-1")
    result = service.get_result("artifact-result-provenance")

    assert provenance.result_fingerprint == result.result_fingerprint
    assert provenance.canonical_payload["result"]["result_fingerprint"] == result.result_fingerprint
    assert provenance.provenance_fingerprint


def test_artifact_provenance_detects_inconsistent_persisted_run_snapshot(db_session):
    service = ResearchExperimentService(db_session)
    service.create_run(definition(), run_id="artifact-corrupt-run")
    service.create_artifact(
        ResearchExperimentArtifactDefinition(
            run_id="artifact-corrupt-run",
            artifact_type="report",
            content_hash="c" * 64,
        ),
        artifact_id="artifact-corrupt-1",
    )

    run = service.repository.get("artifact-corrupt-run")
    run.run_input_fingerprint = "d" * 64
    db_session.commit()

    with pytest.raises(InvalidInputError, match="inconsistent definition snapshot"):
        service.get_artifact_provenance("artifact-corrupt-1")


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



def test_comparison_run_normalizes_identity_and_fingerprints():
    run = ResearchExperimentComparisonRun(
        run_id="  run-001  ",
        experiment_key=" value-quality ",
        definition_version=" 1 ",
        run_input_fingerprint="A" * 64,
        result_fingerprint="B" * 64,
    )

    assert run.run_id == "run-001"
    assert run.experiment_key == "value-quality"
    assert run.definition_version == "1"
    assert run.run_input_fingerprint == "a" * 64
    assert run.result_fingerprint == "b" * 64


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("run_id", " ", "Experiment run id"),
        ("experiment_key", " ", "Experiment key"),
        ("definition_version", " ", "Experiment definition version"),
        ("run_input_fingerprint", "not-a-hash", "Run input fingerprint"),
        ("result_fingerprint", "g" * 64, "Result fingerprint"),
    ],
)
def test_comparison_run_rejects_invalid_identity_fields(field, value, match):
    values = {
        "run_id": "run-001",
        "experiment_key": "value-quality",
        "definition_version": "1",
        "run_input_fingerprint": "a" * 64,
        "result_fingerprint": "b" * 64,
    }
    values[field] = value

    with pytest.raises(InvalidInputError, match=match):
        ResearchExperimentComparisonRun(**values)


def test_comparison_contract_normalizes_selection_fingerprint():
    run_a = ResearchExperimentComparisonRun(
        run_id="run-a",
        experiment_key="value-quality",
        definition_version="1",
        run_input_fingerprint="a" * 64,
        result_fingerprint="b" * 64,
    )
    run_b = ResearchExperimentComparisonRun(
        run_id="run-b",
        experiment_key="value-quality",
        definition_version="1",
        run_input_fingerprint="c" * 64,
        result_fingerprint="d" * 64,
    )

    comparison = ResearchExperimentComparison(
        selection_fingerprint="A" * 64,
        experiment_key="value-quality",
        definition_version="1",
        runs=(run_b, run_a),
    )

    assert comparison.selection_fingerprint == "a" * 64
    assert [run.run_id for run in comparison.runs] == ["run-a", "run-b"]


def test_comparison_contract_rejects_invalid_selection_fingerprint():
    run = ResearchExperimentComparisonRun(
        run_id="run-a",
        experiment_key="value-quality",
        definition_version="1",
        run_input_fingerprint="a" * 64,
        result_fingerprint="b" * 64,
    )
    with pytest.raises(InvalidInputError, match="selection fingerprint"):
        ResearchExperimentComparison(
            selection_fingerprint="not-a-hash",
            experiment_key="value-quality",
            definition_version="1",
            runs=(run, run),
        )


def test_comparison_run_canonical_payload_is_normalized():
    run = ResearchExperimentComparisonRun(
        run_id="  run-a ",
        experiment_key=" value-quality ",
        definition_version=" 1 ",
        run_input_fingerprint="A" * 64,
        result_fingerprint="B" * 64,
    )

    assert run.canonical_payload == {
        "run_id": "run-a",
        "experiment": {"key": "value-quality", "definition_version": "1"},
        "run_input_fingerprint": "a" * 64,
        "result_fingerprint": "b" * 64,
    }

def test_comparison_contract_is_canonical_and_order_independent():
    first = ResearchExperimentComparison(
        selection_fingerprint="a" * 64,
        experiment_key="value-quality",
        definition_version="1",
        runs=(
            ResearchExperimentComparisonRun(
                run_id="run-b",
                experiment_key="value-quality",
                definition_version="1",
                run_input_fingerprint="b" * 64,
                result_fingerprint="2" * 64,
            ),
            ResearchExperimentComparisonRun(
                run_id="run-a",
                experiment_key="value-quality",
                definition_version="1",
                run_input_fingerprint="a" * 64,
                result_fingerprint="1" * 64,
            ),
        ),
    )
    second = ResearchExperimentComparison(
        selection_fingerprint="a" * 64,
        experiment_key="value-quality",
        definition_version="1",
        runs=tuple(reversed(first.runs)),
    )

    assert [run.run_id for run in first.runs] == ["run-a", "run-b"]
    assert first.canonical_payload == second.canonical_payload
    assert first.comparison_fingerprint == second.comparison_fingerprint


def test_comparison_contract_requires_at_least_two_runs():
    run = ResearchExperimentComparisonRun(
        run_id="only-run",
        experiment_key="value-quality",
        definition_version="1",
        run_input_fingerprint="a" * 64,
        result_fingerprint="b" * 64,
    )
    with pytest.raises(InvalidInputError, match="at least two runs"):
        ResearchExperimentComparison(
            selection_fingerprint="c" * 64,
            experiment_key="value-quality",
            definition_version="1",
            runs=(run,),
        )


def test_comparison_contract_rejects_mixed_experiment_identity():
    runs = (
        ResearchExperimentComparisonRun(
            run_id="run-a",
            experiment_key="value-quality",
            definition_version="1",
            run_input_fingerprint="a" * 64,
            result_fingerprint="b" * 64,
        ),
        ResearchExperimentComparisonRun(
            run_id="run-b",
            experiment_key="momentum",
            definition_version="1",
            run_input_fingerprint="c" * 64,
            result_fingerprint="d" * 64,
        ),
    )
    with pytest.raises(InvalidInputError, match="share the comparison experiment identity"):
        ResearchExperimentComparison(
            selection_fingerprint="e" * 64,
            experiment_key="value-quality",
            definition_version="1",
            runs=runs,
        )


def test_compare_runs_resolves_persisted_results(db_session):
    service = ResearchExperimentService(db_session)
    first = service.create_run(definition(), run_id="compare-001")
    second = service.create_run(definition(), run_id="compare-002")
    service.execute_run(
        first.run_id,
        definition(),
        lambda _: ResearchExperimentExecutionResult(
            result_payload={"value": 1}, metrics={"sharpe": 1.1}
        ),
    )
    service.execute_run(
        second.run_id,
        definition(),
        lambda _: ResearchExperimentExecutionResult(
            result_payload={"value": 2}, metrics={"sharpe": 1.3}
        ),
    )

    comparison = service.compare_runs(
        ResearchExperimentRunSelection(
            run_ids=(second.run_id, first.run_id),
            experiment_key="value-quality",
            definition_version="1",
        )
    )

    assert isinstance(comparison, ResearchExperimentComparison)
    assert comparison.selection_fingerprint
    assert comparison.comparison_fingerprint
    assert [run.run_id for run in comparison.runs] == ["compare-001", "compare-002"]
    assert all(run.result_fingerprint for run in comparison.runs)


def test_compare_runs_rejects_missing_persisted_result(db_session):
    service = ResearchExperimentService(db_session)
    first = service.create_run(definition(), run_id="compare-missing-001")
    second = service.create_run(definition(), run_id="compare-missing-002")
    service.execute_run(
        first.run_id,
        definition(),
        lambda _: ResearchExperimentExecutionResult(result_payload={"value": 1}),
    )

    with pytest.raises(ResourceNotFoundError, match="Experiment results not found"):
        service.compare_runs(
            ResearchExperimentRunSelection(
                run_ids=(first.run_id, second.run_id),
                experiment_key="value-quality",
                definition_version="1",
            )
        )


def test_compare_runs_rejects_mixed_persisted_experiment_identity(db_session):
    service = ResearchExperimentService(db_session)
    first = service.create_run(definition(), run_id="compare-mixed-001")
    second = service.create_run(
        definition(experiment_key="momentum"), run_id="compare-mixed-002"
    )
    for run_id, item_definition in (
        (first.run_id, definition()),
        (second.run_id, definition(experiment_key="momentum")),
    ):
        service.execute_run(
            run_id,
            item_definition,
            lambda _: ResearchExperimentExecutionResult(result_payload={"ok": True}),
        )

    with pytest.raises(InvalidInputError, match="same experiment identity"):
        service.compare_runs(
            ResearchExperimentRunSelection(
                run_ids=(first.run_id, second.run_id),
            )
        )


def test_compare_runs_requires_selection_type(db_session):
    service = ResearchExperimentService(db_session)
    with pytest.raises(InvalidInputError, match="ResearchExperimentRunSelection"):
        service.compare_runs(object())
