from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_observation_service import ResearchObservationService


def make_service():
    service = ResearchObservationService.__new__(ResearchObservationService)
    service.db = Mock()
    service.observation_repo = Mock()
    return service


def test_create_observation_normalizes_identity_and_fingerprints_manifest():
    service = make_service()
    service.observation_repo.get_by_identity.return_value = None
    service.observation_repo.create.side_effect = lambda **kwargs: Mock(**kwargs)

    result = service.create_observation(
        security_id=10,
        as_of=datetime(2026, 8, 20, 15, 30),
        observation_key="  roe ",
        definition_version=" 1 ",
        value_numeric=0.18,
        unit="ratio",
        input_manifest={"b": [2, 1], "a": {"x": 1}},
    )

    assert result.security_id == 10
    assert result.as_of == datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    assert result.observation_key == "roe"
    assert result.definition_version == "1"
    assert result.input_manifest == {"a": {"x": 1}, "b": [2, 1]}
    assert len(result.input_fingerprint) == 64


def test_create_observation_is_idempotent_for_same_identity_and_manifest():
    service = make_service()
    existing = Mock(
        input_fingerprint="a" * 64,
        value_numeric=0.18,
        value_text=None,
        unit=None,
    )
    service.observation_repo.get_by_identity.return_value = existing

    manifest = {"source": "pit-snapshot"}
    import hashlib
    import json
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing.input_fingerprint = fingerprint

    assert service.create_observation(
        security_id=10,
        as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        observation_key="roe",
        definition_version="1",
        value_numeric=0.18,
        input_manifest=manifest,
    ) is existing
    service.observation_repo.create.assert_not_called()


def test_create_observation_rejects_same_identity_with_different_value():
    service = make_service()
    manifest = {"source": "pit-snapshot"}
    import hashlib
    import json
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    service.observation_repo.get_by_identity.return_value = Mock(
        input_fingerprint=fingerprint,
        value_numeric=0.18,
        value_text=None,
        unit="ratio",
    )

    with pytest.raises(InvalidInputError):
        service.create_observation(
            security_id=10,
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            observation_key="roe",
            definition_version="1",
            value_numeric=0.19,
            unit="ratio",
            input_manifest=manifest,
        )


def test_create_observation_rejects_same_identity_with_different_manifest():
    service = make_service()
    service.observation_repo.get_by_identity.return_value = Mock(
        input_fingerprint="a" * 64
    )

    with pytest.raises(InvalidInputError):
        service.create_observation(
            security_id=10,
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            observation_key="roe",
            definition_version="1",
            value_numeric=0.18,
            input_manifest={"source": "different"},
        )


def test_create_observation_rejects_future_as_of():
    service = make_service()

    with pytest.raises(InvalidInputError):
        service.create_observation(
            security_id=10,
            as_of=datetime(2999, 1, 1, tzinfo=timezone.utc),
            observation_key="roe",
            definition_version="1",
            value_numeric=0.18,
            input_manifest={},
        )


def test_create_observation_requires_a_value():
    service = make_service()

    with pytest.raises(InvalidInputError):
        service.create_observation(
            security_id=10,
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            observation_key="roe",
            definition_version="1",
            input_manifest={},
        )


def test_create_observation_rejects_both_value_types():
    service = make_service()

    with pytest.raises(InvalidInputError):
        service.create_observation(
            security_id=10,
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            observation_key="roe",
            definition_version="1",
            value_numeric=0.18,
            value_text="18%",
            input_manifest={},
        )


def test_create_observation_requires_nonempty_identity():
    service = make_service()

    with pytest.raises(InvalidInputError):
        service.create_observation(
            security_id=10,
            as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
            observation_key=" ",
            definition_version="1",
            value_numeric=0.18,
            input_manifest={},
        )
