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


def test_get_latest_for_security_as_of_delegates_to_pit_query():
    db = Mock()
    repository = ResearchObservationRepository(db)
    db.scalars.return_value.all.return_value = ["one", "two"]

    as_of = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    assert repository.get_latest_for_security_as_of(10, as_of) == ["one", "two"]
    db.scalars.assert_called_once()


def test_get_latest_for_security_as_of_uses_security_and_as_of_boundary():
    db = Mock()
    repository = ResearchObservationRepository(db)
    db.scalars.return_value.all.return_value = []

    as_of = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    repository.get_latest_for_security_as_of(10, as_of)

    statement = db.scalars.call_args.args[0]
    sql = str(statement)
    params = statement.compile().params

    assert "research_observations.security_id" in sql
    assert "research_observations.as_of <=" in sql
    assert 10 in params.values()
    assert as_of in params.values()
