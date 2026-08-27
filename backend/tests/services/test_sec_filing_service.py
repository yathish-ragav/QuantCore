from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.enums import FilingEventType
from quantcore.models.provenance import DataSource
from quantcore.schemas.sec_filing import SECFilingData
from quantcore.services.sec_filing_service import (
    SECFilingService,
    SECFilingSyncResult,
)


def make_company():
    company = Mock()
    company.id = 1
    return company


def make_security(company):
    security = Mock()
    security.id = 10
    security.company_id = company.id
    security.symbol = "AAPL"
    security.company = company
    return security


def make_filing(accession="0000320193-24-000123", amendment=False):
    return SECFilingData(
        accession_number=accession,
        filing_date=date(2024, 11, 1),
        report_date=date(2024, 9, 28),
        acceptance_datetime=datetime(2024, 11, 1, 16, 30, tzinfo=timezone.utc),
        form="10-K/A" if amendment else "10-K",
        primary_document="aapl.htm",
        primary_doc_description="Annual Report",
        is_xbrl=True,
        is_inline_xbrl=True,
        fiscal_year=2024,
        fiscal_period="FY",
        is_amendment=amendment,
        filing_url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl.htm",
    )


def make_service():
    db = Mock()
    service = SECFilingService.__new__(SECFilingService)
    service.db = db
    service.provider = Mock()
    service.provider.SOURCE = "SEC"
    service.security_repo = Mock()
    service.filing_repo = Mock()
    return service, db


def test_get_filings():
    service, _ = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    expected = [Mock()]
    service.filing_repo.get_for_company.return_value = expected

    assert service.get_filings("AAPL") == expected
    service.filing_repo.get_for_company.assert_called_once_with(company.id)


def test_sync_filings_creates_filing_and_event():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_sec_filings.return_value = [make_filing()]
    service.filing_repo.get_by_accession.return_value = None
    created = Mock()
    created.id = 100
    service.filing_repo.create.return_value = created
    service.filing_repo.get_event.return_value = None

    result = service.sync_filings("AAPL")

    assert result == SECFilingSyncResult(
        created=1,
        updated=0,
        unchanged=0,
        events_created=1,
        records_processed=1,
    )
    service.filing_repo.create.assert_called_once()
    service.filing_repo.create_event.assert_called_once()
    event_kwargs = service.filing_repo.create_event.call_args.kwargs
    assert event_kwargs["filing_id"] == 100
    assert event_kwargs["event_type"] is FilingEventType.FILED
    db.flush.assert_called_once()
    db.commit.assert_called_once()


def test_sync_filings_creates_amendment_event():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_sec_filings.return_value = [make_filing(amendment=True)]
    service.filing_repo.get_by_accession.return_value = None
    created = Mock()
    created.id = 101
    service.filing_repo.create.return_value = created
    service.filing_repo.get_event.return_value = None

    service.sync_filings("AAPL")

    event_kwargs = service.filing_repo.create_event.call_args.kwargs
    assert event_kwargs["event_type"] is FilingEventType.AMENDED
    db.commit.assert_called_once()


def test_sync_filings_is_idempotent_for_existing_filing_and_event():
    service, db = make_service()
    company = make_company()
    existing = Mock()
    existing.id = 100
    incoming = make_filing()
    for field in (
        "filing_date",
        "report_date", "acceptance_datetime", "form", "act",
        "file_number", "film_number", "items", "primary_document",
        "primary_doc_description", "is_xbrl", "is_inline_xbrl",
        "fiscal_year", "fiscal_period", "is_amendment", "filing_url",
    ):
        setattr(existing, field, getattr(incoming, field))
    existing.source = DataSource.SEC
    existing.source_reference = incoming.accession_number
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_sec_filings.return_value = [incoming]
    service.filing_repo.get_by_accession.return_value = existing
    service.filing_repo.get_event.return_value = Mock()

    result = service.sync_filings("AAPL")

    assert result == SECFilingSyncResult(
        created=0,
        updated=0,
        unchanged=1,
        events_created=0,
        records_processed=1,
    )
    service.filing_repo.create.assert_not_called()
    service.filing_repo.create_event.assert_not_called()
    db.commit.assert_called_once()


def test_sync_filings_counts_updated_metadata_and_new_event():
    service, db = make_service()
    company = make_company()
    existing = Mock()
    existing.id = 100
    for field in (
        "report_date", "acceptance_datetime", "form", "act",
        "file_number", "film_number", "items", "primary_document",
        "primary_doc_description", "is_xbrl", "is_inline_xbrl",
        "fiscal_year", "fiscal_period", "is_amendment", "filing_url",
    ):
        setattr(existing, field, None)
    existing.source = DataSource.SEC
    existing.source_reference = "old"
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_sec_filings.return_value = [make_filing()]
    service.filing_repo.get_by_accession.return_value = existing
    service.filing_repo.get_event.return_value = None

    result = service.sync_filings("AAPL")

    assert result == SECFilingSyncResult(
        created=0,
        updated=1,
        unchanged=0,
        events_created=1,
        records_processed=1,
    )
    db.commit.assert_called_once()


def test_sync_filings_rolls_back_on_provider_error():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_sec_filings.side_effect = RuntimeError("provider error")

    with pytest.raises(RuntimeError, match="provider error"):
        service.sync_filings("AAPL")

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
