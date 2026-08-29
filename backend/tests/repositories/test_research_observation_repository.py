from datetime import datetime, timezone
from unittest.mock import Mock

from quantcore.repositories.research_observation_repository import (
    ResearchObservationRepository,
)


def test_get_by_identity_uses_all_identity_fields():
    db = Mock()
    repository = ResearchObservationRepository(db)
    db.scalar.return_value = "observation"

    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)
    result = repository.get_by_identity(
        security_id=10,
        as_of=as_of,
        observation_key="roe",
        definition_version="1",
    )

    assert result == "observation"
    db.scalar.assert_called_once()


def test_get_for_security_as_of_returns_repository_rows():
    db = Mock()
    repository = ResearchObservationRepository(db)
    db.scalars.return_value.all.return_value = ["one", "two"]

    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)
    assert repository.get_for_security_as_of(10, as_of) == ["one", "two"]
