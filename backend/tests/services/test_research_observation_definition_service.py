from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.pit_alignment_service import PITAlignedSnapshot
from quantcore.services.research_observation_definition_service import (
    ResearchObservationDefinitionRegistry,
    ResearchObservationDefinitionService,
    ResearchObservationValue,
)


@dataclass(frozen=True)
class ROEDefinition:
    observation_key: str = "roe"
    definition_version: str = "1"

    def compute(self, snapshot):
        return ResearchObservationValue(
            value_numeric=0.18,
            unit="ratio",
            input_manifest={"source": "pit-snapshot"},
        )


def make_service():
    service = ResearchObservationDefinitionService.__new__(
        ResearchObservationDefinitionService
    )
    service.db = Mock()
    service.pit_alignment_service = Mock()
    service.observation_service = Mock()
    service.definition_registry = ResearchObservationDefinitionRegistry([ROEDefinition()])
    return service


def make_snapshot():
    return PITAlignedSnapshot(
        symbol="AAPL",
        security_id=10,
        company_id=20,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        prices=(Mock(),),
        income_statements=(),
        balance_sheets=(),
        cash_flow_statements=(),
        corporate_actions=(),
        sec_xbrl_facts=(),
        macro_observations={},
    )


def test_registry_resolves_versioned_definition():
    definition = ROEDefinition()
    registry = ResearchObservationDefinitionRegistry([definition])

    assert registry.get(" roe ", " 1 ") is definition


def test_registry_rejects_duplicate_definition_identity():
    with pytest.raises(InvalidInputError):
        ResearchObservationDefinitionRegistry([ROEDefinition(), ROEDefinition()])


def test_registry_rejects_missing_definition():
    registry = ResearchObservationDefinitionRegistry()

    with pytest.raises(ResourceNotFoundError):
        registry.get("roe", "1")


def test_compute_observation_uses_one_pit_snapshot_and_persists_provenance():
    service = make_service()
    snapshot = make_snapshot()
    service.pit_alignment_service.get_snapshot.return_value = snapshot
    stored = Mock()
    service.observation_service.create_observation.return_value = stored

    result = service.compute_observation(
        " aapl ",
        as_of=datetime(2026, 8, 20, 15, 30),
        observation_key=" roe ",
        definition_version=" 1 ",
        macro_series_ids=["gdp"],
    )

    assert result is stored
    service.pit_alignment_service.get_snapshot.assert_called_once_with(
        " aapl ",
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        macro_series_ids=("gdp",),
    )
    service.observation_service.create_observation.assert_called_once_with(
        security_id=10,
        as_of=snapshot.as_of,
        observation_key="roe",
        definition_version="1",
        value_numeric=0.18,
        value_text=None,
        unit="ratio",
        input_manifest={
            "definition": {"observation_key": "roe", "definition_version": "1"},
            "pit_snapshot": {
                "symbol": "AAPL",
                "security_id": 10,
                "company_id": 20,
                "as_of": "2026-08-20T15:30:00+00:00",
            },
            "inputs": {"source": "pit-snapshot"},
        },
    )


def test_compute_observation_rejects_future_timestamp_before_snapshot():
    service = make_service()

    with pytest.raises(InvalidInputError):
        service.compute_observation(
            "AAPL",
            as_of=datetime(2999, 1, 1, tzinfo=timezone.utc),
            observation_key="roe",
            definition_version="1",
        )

    service.pit_alignment_service.get_snapshot.assert_not_called()


def test_compute_observation_requires_definition_value():
    class EmptyDefinition:
        observation_key = "empty"
        definition_version = "1"

        def compute(self, snapshot):
            return ResearchObservationValue(input_manifest={})

    service = ResearchObservationDefinitionService.__new__(
        ResearchObservationDefinitionService
    )
    service.db = Mock()
    service.pit_alignment_service = Mock()
    service.observation_service = Mock()
    service.definition_registry = ResearchObservationDefinitionRegistry([EmptyDefinition()])
    service.pit_alignment_service.get_snapshot.return_value = make_snapshot()

    with pytest.raises(InvalidInputError):
        service.compute_observation(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            observation_key="empty",
            definition_version="1",
        )

    service.observation_service.create_observation.assert_not_called()
