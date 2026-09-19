from datetime import date, datetime, timezone
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
        effective_from=date(2025, 1, 1),
        known_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
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
        effective_from=date.today(),
        known_at=datetime.now(timezone.utc),
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        is_current=True,
    )
    db.scalars.return_value.all.return_value = [history]

    repository.mark_all_not_current(1)

    assert history.is_current is False


def test_mark_not_current_closes_effective_interval():
    repository, db = make_repository()
    history = SecurityIdentifierHistory(
        security_id=1,
        symbol="OLD",
        exchange="NASDAQ",
        effective_from=date(2020, 1, 1),
        effective_to=None,
        known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
        first_seen_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        is_current=True,
    )
    db.scalars.return_value.all.return_value = [history]

    repository.mark_not_current(
        security_id=1,
        except_symbol="NEW",
        except_exchange="NASDAQ",
        effective_to=date(2026, 2, 1),
    )

    assert history.is_current is False
    assert history.effective_to == date(2026, 2, 1)


def test_upsert_does_not_move_known_at_forward():
    repository, db = make_repository()
    original_known_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    history = SecurityIdentifierHistory(
        security_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
        effective_from=date(2025, 1, 1),
        known_at=original_known_at,
        first_seen_at=original_known_at,
        last_seen_at=original_known_at,
        is_current=True,
    )
    db.scalar.return_value = history
    observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    result = repository.upsert(1, "AAPL", "NASDAQ", observed_at, source="SEC")

    assert result is history
    assert history.known_at == original_known_at
    assert history.first_seen_at == original_known_at
    assert history.last_seen_at == observed_at


def test_get_for_security_as_of_respects_knowledge_cutoff():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from quantcore.db.database import Base
    from quantcore.models.company import Company
    from quantcore.models.security import Security

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        company = Company(cik="0000000001", name="Test Company")
        session.add(company)
        session.flush()
        security = Security(
            company_id=company.id,
            symbol="OLD",
            exchange="NASDAQ",
        )
        session.add(security)
        session.flush()

        early = datetime(2019, 2, 1, tzinfo=timezone.utc)
        late = datetime(2021, 1, 1, tzinfo=timezone.utc)
        session.add_all([
            SecurityIdentifierHistory(
                security_id=security.id,
                symbol="OLD",
                exchange="NASDAQ",
                effective_from=date(2019, 1, 1),
                effective_to=date(2020, 6, 1),
                known_at=early,
                first_seen_at=early,
                last_seen_at=datetime(2020, 5, 1, tzinfo=timezone.utc),
                is_current=False,
            ),
            SecurityIdentifierHistory(
                security_id=security.id,
                symbol="NEW",
                exchange="NASDAQ",
                effective_from=date(2020, 6, 1),
                effective_to=None,
                known_at=late,
                first_seen_at=late,
                last_seen_at=late,
                is_current=True,
            ),
        ])
        session.commit()

        repository = SecurityIdentifierHistoryRepository(session)
        result = repository.get_for_security_as_of(
            security.id,
            effective_on=date(2020, 3, 1),
            known_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )

        assert [(row.symbol, row.exchange) for row in result] == [("OLD", "NASDAQ")]
    finally:
        session.close()
        engine.dispose()
