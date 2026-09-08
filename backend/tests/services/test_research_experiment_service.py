from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_experiment_service import (
    ResearchExperimentDefinition,
    ResearchExperimentDefinitionRegistry,
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
