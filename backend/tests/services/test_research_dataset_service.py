from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_dataset_service import (
    ResearchDatasetService,
    ResearchFeature,
    ResearchFeatureVector,
)


def make_service(observations=()):
    service = ResearchDatasetService.__new__(ResearchDatasetService)
    service.db = Mock()
    service.observation_service = Mock()
    service.observation_service.get_latest_for_symbol_as_of.return_value = list(observations)
    return service


def make_observation(
    key,
    version="1",
    *,
    security_id=10,
    as_of=None,
    value_numeric=0.12,
    value_text=None,
    unit="ratio",
    fingerprint=None,
):
    observation = Mock()
    observation.security_id = security_id
    observation.observation_key = key
    observation.definition_version = version
    observation.as_of = as_of or datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc)
    observation.value_numeric = value_numeric
    observation.value_text = value_text
    observation.unit = unit
    observation.input_fingerprint = fingerprint or (key[0] * 64)
    observation.input_manifest = {"source": key}
    return observation


def test_build_feature_vector_uses_latest_pit_observations_and_normalizes_symbol():
    observations = (
        make_observation("operating_margin", value_numeric=0.18),
        make_observation("net_margin", value_numeric=0.12),
    )
    service = make_service(observations)

    result = service.build_feature_vector(
        " aapl ",
        as_of=datetime(2026, 8, 20, 15, 30),
    )

    assert isinstance(result, ResearchFeatureVector)
    assert result.symbol == "AAPL"
    assert result.security_id == 10
    assert result.as_of == datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    assert [feature.observation_key for feature in result.features] == [
        "net_margin",
        "operating_margin",
    ]
    assert all(isinstance(feature, ResearchFeature) for feature in result.features)
    service.observation_service.get_latest_for_symbol_as_of.assert_called_once_with(
        "AAPL",
        as_of=datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc),
    )


def test_build_feature_vector_preserves_observation_provenance_and_values():
    observation = make_observation(
        "net_margin",
        value_numeric=0.12,
        unit="ratio",
        fingerprint="a" * 64,
    )
    service = make_service((observation,))

    result = service.build_feature_vector(
        "AAPL",
        as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )

    feature = result.features[0]
    assert feature.observation_as_of == observation.as_of
    assert feature.value_numeric == 0.12
    assert feature.value_text is None
    assert feature.unit == "ratio"
    assert feature.input_fingerprint == "a" * 64
    assert feature.input_manifest == {"source": "net_margin"}


def test_build_feature_vector_can_select_versioned_identities_in_requested_order():
    observations = (
        make_observation("net_margin", "1", value_numeric=0.12),
        make_observation("net_margin", "2", value_numeric=0.14),
        make_observation("operating_margin", "1", value_numeric=0.18),
    )
    service = make_service(observations)

    result = service.build_feature_vector(
        "AAPL",
        as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        definition_identities=[(" operating_margin ", " 1 "), ("net_margin", "2")],
    )

    assert [(item.observation_key, item.definition_version) for item in result.features] == [
        ("operating_margin", "1"),
        ("net_margin", "2"),
    ]


def test_build_feature_vector_rejects_missing_requested_identity():
    service = make_service((make_observation("net_margin"),))

    with pytest.raises(ResourceNotFoundError, match="operating_margin v1"):
        service.build_feature_vector(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            definition_identities=[("net_margin", "1"), ("operating_margin", "1")],
        )


def test_build_feature_vector_rejects_duplicate_requested_identity():
    service = make_service((make_observation("net_margin"),))

    with pytest.raises(InvalidInputError, match="must not contain duplicates"):
        service.build_feature_vector(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            definition_identities=[("net_margin", "1"), (" net_margin ", " 1 ")],
        )

    service.observation_service.get_latest_for_symbol_as_of.assert_not_called()


def test_build_feature_vector_rejects_empty_requested_identity_selection():
    service = make_service((make_observation("net_margin"),))

    with pytest.raises(InvalidInputError, match="At least one definition identity"):
        service.build_feature_vector(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            definition_identities=[],
        )

    service.observation_service.get_latest_for_symbol_as_of.assert_not_called()


def test_build_feature_vector_rejects_empty_materialized_dataset():
    service = make_service(())

    with pytest.raises(ResourceNotFoundError, match="No research observations available"):
        service.build_feature_vector(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )


def test_build_feature_vector_rejects_future_observation_boundary():
    service = make_service(
        (
            make_observation(
                "net_margin",
                as_of=datetime(2026, 8, 21, tzinfo=timezone.utc),
            ),
        )
    )

    with pytest.raises(InvalidInputError, match="exceeds the requested as-of boundary"):
        service.build_feature_vector(
            "AAPL",
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )


def test_feature_vector_input_fingerprint_is_deterministic_and_content_bound():
    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)
    service = make_service((make_observation("net_margin", as_of=as_of),))

    first = service.build_feature_vector("AAPL", as_of=as_of)
    second = service.build_feature_vector("AAPL", as_of=as_of)

    assert len(first.input_fingerprint) == 64
    assert first.input_fingerprint == second.input_fingerprint

    changed = ResearchFeatureVector(
        symbol=first.symbol,
        security_id=first.security_id,
        as_of=first.as_of,
        features=(
            ResearchFeature(
                observation_key="net_margin",
                definition_version="1",
                observation_as_of=as_of,
                value_numeric=0.99,
                value_text=None,
                unit="ratio",
                input_fingerprint=first.features[0].input_fingerprint,
                input_manifest=first.features[0].input_manifest,
            ),
        ),
    )
    assert changed.input_fingerprint != first.input_fingerprint


def test_feature_vector_input_fingerprint_changes_when_pit_boundary_changes():
    first = ResearchFeatureVector(
        symbol="AAPL",
        security_id=10,
        as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        features=(),
    )
    second = ResearchFeatureVector(
        symbol="AAPL",
        security_id=10,
        as_of=datetime(2026, 8, 21, tzinfo=timezone.utc),
        features=(),
    )

    assert first.input_fingerprint != second.input_fingerprint

def test_feature_vector_input_fingerprint_is_independent_of_feature_order():
    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)
    first = ResearchFeatureVector(
        symbol="AAPL",
        security_id=10,
        as_of=as_of,
        features=(
            ResearchFeature(
                observation_key="z_metric",
                definition_version="1",
                observation_as_of=as_of,
                value_numeric=2.0,
                value_text=None,
                unit="ratio",
                input_fingerprint="a" * 64,
                input_manifest={},
            ),
            ResearchFeature(
                observation_key="a_metric",
                definition_version="1",
                observation_as_of=as_of,
                value_numeric=1.0,
                value_text=None,
                unit="ratio",
                input_fingerprint="b" * 64,
                input_manifest={},
            ),
        ),
    )
    second = ResearchFeatureVector(
        symbol=first.symbol,
        security_id=first.security_id,
        as_of=first.as_of,
        features=tuple(reversed(first.features)),
    )

    assert first.input_fingerprint == second.input_fingerprint
