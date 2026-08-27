from datetime import datetime, timezone
from unittest.mock import Mock

from quantcore.core.enums import CorporateActionType
from quantcore.repositories.corporate_action_revision_repository import (
    CorporateActionRevisionRepository,
)


def make_repository():
    db = Mock()
    return CorporateActionRevisionRepository(db), db


def test_get_next_revision_number_starts_at_one():
    repository, db = make_repository()
    db.scalar.return_value = None

    assert repository.get_next_revision_number(10) == 1


def test_get_next_revision_number_increments_existing_revision():
    repository, db = make_repository()
    db.scalar.return_value = 2

    assert repository.get_next_revision_number(10) == 3


def test_create_adds_revision_without_transaction_control():
    repository, db = make_repository()
    revision = repository.create(
        action_id=10,
        security_id=1,
        revision_number=1,
        effective_date=datetime(2024, 8, 12).date(),
        action_type=CorporateActionType.STOCK_SPLIT,
        split_ratio=4.0,
        known_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )

    db.add.assert_called_once_with(revision)
    assert revision.action_id == 10
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_latest_for_security_as_of_builds_ranked_query():
    repository, db = make_repository()
    revision = Mock()
    db.scalars.return_value.all.return_value = [revision]

    result = repository.get_latest_for_security_as_of(
        1,
        datetime(2026, 1, 5, tzinfo=timezone.utc),
    )

    assert result == [revision]
    db.scalars.assert_called_once()
