from datetime import date, datetime, timezone
from unittest.mock import Mock

from quantcore.core.enums import FilingEventType
from quantcore.models.sec_filing import FilingEvent, SECFiling
from quantcore.repositories.sec_filing_repository import SECFilingRepository


def make_repository():
    db = Mock()
    return SECFilingRepository(db), db


def test_get_by_accession():
    repository, db = make_repository()
    filing = Mock(spec=SECFiling)
    db.scalar.return_value = filing

    assert repository.get_by_accession("0000320193-24-000123") == filing
    db.scalar.assert_called_once()


def test_get_for_company():
    repository, db = make_repository()
    filings = [Mock(spec=SECFiling)]
    db.scalars.return_value.all.return_value = filings

    assert repository.get_for_company(1) == filings
    db.scalars.assert_called_once()


def test_create():
    repository, db = make_repository()
    filing = repository.create(
        company_id=1,
        accession_number="0000320193-24-000123",
        filing_date=date(2024, 11, 1),
        form="10-K",
    )

    db.add.assert_called_once_with(filing)
    assert isinstance(filing, SECFiling)


def test_create_event():
    repository, db = make_repository()
    occurred_at = datetime(2024, 11, 1, tzinfo=timezone.utc)
    event = repository.create_event(
        filing_id=1,
        event_type=FilingEventType.FILED,
        occurred_at=occurred_at,
    )

    db.add.assert_called_once_with(event)
    assert isinstance(event, FilingEvent)
