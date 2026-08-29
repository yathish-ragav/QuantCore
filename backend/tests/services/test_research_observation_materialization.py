from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.pit_alignment_service import PITAlignedSnapshot
from quantcore.services.research_observation_definition_service import (
    ResearchObservationDefinitionService,
    ResearchObservationValue,
)


@dataclass(frozen=True)
class MetricDefinition:
    observation_key: str
    definition_version: str = "1"
    value_numeric: float = 0.1

    def compute(self, snapshot):
        return ResearchObservationValue(
            value_numeric=self.value_numeric,
            unit="ratio",
            input_manifest={"source": self.observation_key},
        )


def make_service(definitions):
    service = ResearchObservationDefinitionService.__new__(
        ResearchObservationDefinitionService
    )
    service.db = Mock()
    service.pit_alignment_service = Mock()
    service.observation_service = Mock()
    from quantcore.services.research_observation_definition_service import (
        ResearchObservationDefinitionRegistry,
    )

    service.definition_registry = ResearchObservationDefinitionRegistry(definitions)
    return service


def make_snapshot():
    return PITAlignedSnapshot(
        symbol="AAPL",
        security_id=10,
        company_id=20,
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        prices=(),
        income_statements=(),
        balance_sheets=(),
        cash_flow_statements=(),
        corporate_actions=(),
        sec_xbrl_facts=(),
        macro_observations={},
    )


def test_materialize_observations_uses_one_shared_pit_snapshot():
    definitions = (
        MetricDefinition("net_margin", value_numeric=0.12),
        MetricDefinition("operating_margin", value_numeric=0.18),
        MetricDefinition("fcf_margin", value_numeric=0.15),
    )
    service = make_service(definitions)
    snapshot = make_snapshot()
    service.pit_alignment_service.get_snapshot.return_value = snapshot
    service.observation_service.create_observation.side_effect = lambda **kwargs: Mock(
        **kwargs
    )

    result = service.materialize_observations(
        " aapl ",
        as_of=datetime(2026, 8, 20, 15, 30),
        macro_series_ids=["gdp"],
    )

    assert len(result) == 3
    service.pit_alignment_service.get_snapshot.assert_called_once_with(
        " aapl ",
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
        macro_series_ids=("gdp",),
    )
    assert service.observation_service.create_observation.call_count == 3
    assert [
        call.kwargs["observation_key"]
        for call in service.observation_service.create_observation.call_args_list
    ] == ["net_margin", "operating_margin", "fcf_margin"]
    for call in service.observation_service.create_observation.call_args_list:
        assert call.kwargs["security_id"] == 10
        assert call.kwargs["as_of"] == snapshot.as_of
        assert call.kwargs["input_manifest"]["pit_snapshot"]["as_of"] == snapshot.as_of.isoformat()


def test_materialize_observations_can_select_versioned_identities():
    definitions = (
        MetricDefinition("net_margin", "1", 0.12),
        MetricDefinition("net_margin", "2", 0.14),
        MetricDefinition("operating_margin", "1", 0.18),
    )
    service = make_service(definitions)
    service.pit_alignment_service.get_snapshot.return_value = make_snapshot()

    service.materialize_observations(
        "AAPL",
        as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        definition_identities=[(" net_margin ", " 2 "), ("operating_margin", "1")],
    )

    assert [
        call.kwargs["observation_key"]
        for call in service.observation_service.create_observation.call_args_list
    ] == ["net_margin", "operating_margin"]
    assert [
        call.kwargs["definition_version"]
        for call in service.observation_service.create_observation.call_args_list
    ] == ["2", "1"]


def test_materialize_observations_computes_every_definition_before_persisting():
    class FailingDefinition(MetricDefinition):
        def compute(self, snapshot):
            raise InvalidInputError("definition failed")

    service = make_service(
        (
            MetricDefinition("net_margin"),
            FailingDefinition("operating_margin"),
        )
    )
    service.pit_alignment_service.get_snapshot.return_value = make_snapshot()

    with pytest.raises(InvalidInputError, match="definition failed"):
        service.materialize_observations(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )

    service.observation_service.create_observation.assert_not_called()


def test_materialize_observations_rejects_empty_selection_before_snapshot():
    service = make_service((MetricDefinition("net_margin"),))

    with pytest.raises(InvalidInputError, match="At least one definition identity"):
        service.materialize_observations(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            definition_identities=[],
        )

    service.pit_alignment_service.get_snapshot.assert_not_called()


def test_materialize_observations_rejects_duplicate_identity_before_snapshot():
    service = make_service((MetricDefinition("net_margin"),))

    with pytest.raises(InvalidInputError, match="must not contain duplicates"):
        service.materialize_observations(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            definition_identities=[("net_margin", "1"), (" net_margin ", " 1 ")],
        )

    service.pit_alignment_service.get_snapshot.assert_not_called()


def test_materialize_observations_rejects_unknown_identity_before_snapshot():
    service = make_service((MetricDefinition("net_margin"),))

    with pytest.raises(ResourceNotFoundError, match="Research observation definition not found"):
        service.materialize_observations(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            definition_identities=[("unknown", "1")],
        )

    service.pit_alignment_service.get_snapshot.assert_not_called()
