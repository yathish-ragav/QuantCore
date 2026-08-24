from datetime import datetime, timezone
from unittest.mock import Mock

from quantcore.models.security_identifier_history import SecurityIdentifierHistory
from quantcore.repositories.security_identifier_history_repository import (
    SecurityIdentifierHistoryRepository,
)


def make_repository():
    db = Mock()
    return SecurityIdentifierHistoryRepository(db), db


def test_upsert_creates_history_row():
    repository, db = make_repository()
    db.scalar.return_value = None
    observed_at = datetime.now(timezone.utc)

    result = repository.upsert(1, "AAPL", "NASDAQ", observed_at)

    assert isinstance(result, SecurityIdentifierHistory)
    assert result.security_id == 1
    assert result.symbol == "AAPL"
    assert result.exchange == "NASDAQ"
    assert result.first_seen_at == observed_at
    assert result.last_seen_at == observed_at
    assert result.is_current is True
    db.add.assert_called_once_with(result)


def test_upsert_updates_existing_history():
    repository, db = make_repository()
    history = SecurityIdentifierHistory(
        security_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
        first_seen_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        last_seen_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        is_current=False,
    )
    db.scalar.return_value = history
    observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    result = repository.upsert(1, "AAPL", "NASDAQ", observed_at)

    assert result is history
    assert history.last_seen_at == observed_at
    assert history.is_current is True
    db.add.assert_not_called()


def test_mark_all_not_current_marks_current_rows_inactive():
    repository, db = make_repository()
    history = SecurityIdentifierHistory(
        security_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        is_current=True,
    )
    db.scalars.return_value.all.return_value = [history]

    repository.mark_all_not_current(1)

    assert history.is_current is False
