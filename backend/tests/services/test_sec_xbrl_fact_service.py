from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from quantcore.models.provenance import DataSource
from quantcore.schemas.sec_xbrl_fact import SECXBRLFactObservationData
from quantcore.services.sec_xbrl_fact_service import SECXBRLFactService, SECXBRLFactSyncResult


def make_service():
    db = Mock()
    service = SECXBRLFactService.__new__(SECXBRLFactService)
    service.db = db
    service.provider = Mock()
    service.provider.SOURCE = "SEC"
    service.security_repo = Mock()
    service.filing_repo = Mock()
    service.fact_repo = Mock()
    return service, db


def make_security_and_company():
    company = Mock(id=1, cik="0000320193")
    security = Mock(id=10, company_id=1, symbol="AAPL", company=company)
    return security, company


def make_fact(accession, value):
    return SECXBRLFactObservationData(
        taxonomy="us-gaap",
        concept="Revenue",
        unit="USD",
        value=Decimal(value),
        period_start=date(2023, 10, 1),
        period_end=date(2024, 9, 28),
        filed_at=date(2024, 11, 1),
        accession_number=accession,
        form="10-K",
        fiscal_year=2024,
        fiscal_period="FY",
        frame="CY2024",
        qtrs=4,
    )


def test_sync_facts_creates_and_keeps_accession_revision_identity():
    service, db = make_service()
    security, company = make_security_and_company()
    service.security_repo.get_by_symbol.return_value = security
    first = make_fact("0000320193-24-000123", "100")
    second = make_fact("0000320193-25-000010", "110")
    service.provider.get_sec_xbrl_fact_observations.return_value = [first, second]
    service.fact_repo.get_by_identity.side_effect = [None, None]
    filing = Mock(id=55, acceptance_datetime=datetime(2024, 11, 1, tzinfo=timezone.utc))
    service.filing_repo.get_by_accession.return_value = filing

    result = service.sync_facts("AAPL")

    assert result == SECXBRLFactSyncResult(created=2, unchanged=0, records_processed=2)
    assert service.fact_repo.create.call_count == 2
    first_kwargs = service.fact_repo.create.call_args_list[0].kwargs
    assert len(first_kwargs["identity_hash"]) == 64
    assert first_kwargs["company_id"] == company.id
    assert first_kwargs["filing_id"] == 55
    assert first_kwargs["source"] is DataSource.SEC
    db.commit.assert_called_once()
    assert service.filing_repo.get_by_accession.call_count == 2


def test_sync_facts_is_idempotent():
    service, db = make_service()
    security, _ = make_security_and_company()
    service.security_repo.get_by_symbol.return_value = security
    incoming = make_fact("0000320193-24-000123", "100")
    service.provider.get_sec_xbrl_fact_observations.return_value = [incoming]
    service.fact_repo.get_by_identity.return_value = Mock()

    result = service.sync_facts("AAPL")

    assert result == SECXBRLFactSyncResult(created=0, unchanged=1, records_processed=1)
    service.fact_repo.create.assert_not_called()
    db.commit.assert_called_once()


def test_sync_facts_rolls_back_on_provider_error():
    service, db = make_service()
    security, _ = make_security_and_company()
    service.security_repo.get_by_symbol.return_value = security
    service.provider.get_sec_xbrl_fact_observations.side_effect = RuntimeError("provider error")

    try:
        service.sync_facts("AAPL")
    except RuntimeError as exc:
        assert str(exc) == "provider error"
    else:
        raise AssertionError("expected provider error")

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
