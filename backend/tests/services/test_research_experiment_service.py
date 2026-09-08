from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_experiment_service import (
    ResearchExperimentDefinition,
    ResearchExperimentDefinitionRegistry,
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

    from quantcore.models.research_experiment import ResearchExperimentRun

    engine = create_engine("sqlite://")
    ResearchExperimentRun.__table__.create(engine)
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
