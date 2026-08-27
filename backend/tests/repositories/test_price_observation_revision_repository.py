from datetime import datetime, timezone
from unittest.mock import Mock

from quantcore.repositories.price_observation_revision_repository import (
    PriceObservationRevisionRepository,
)


def test_get_next_revision_number_starts_at_one():
    db = Mock()
    db.scalar.return_value = None
    repo = PriceObservationRevisionRepository(db)

    assert repo.get_next_revision_number(10) == 1


def test_get_next_revision_number_increments_existing_revision():
    db = Mock()
    db.scalar.return_value = 3
    repo = PriceObservationRevisionRepository(db)

    assert repo.get_next_revision_number(10) == 4


def test_get_for_price_returns_revisions():
    db = Mock()
    revisions = [Mock(), Mock()]
    db.scalars.return_value.all.return_value = revisions
    repo = PriceObservationRevisionRepository(db)

    assert repo.get_for_price(10) == revisions
    db.scalars.return_value.all.assert_called_once()


def test_get_latest_for_security_as_of_returns_pit_revisions():
    db = Mock()
    revisions = [Mock(), Mock()]
    db.scalars.return_value.all.return_value = revisions
    repo = PriceObservationRevisionRepository(db)
    as_of = datetime(2026, 1, 5, tzinfo=timezone.utc)

    assert repo.get_latest_for_security_as_of(10, as_of) == revisions
    db.scalars.return_value.all.assert_called_once()
