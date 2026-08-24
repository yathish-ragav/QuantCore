from unittest.mock import Mock, call

import pytest

from quantcore.models.company import Company
from quantcore.models.security import Security, SecurityStatus
from quantcore.models.provenance import CompanyField, DataSource
from quantcore.universe.models import UniverseCompany
from quantcore.universe.service import UniverseService


def make_company(
    cik="0000320193",
    symbol="AAPL",
    name="Apple Inc.",
    exchange="NASDAQ",
):
    return UniverseCompany(
        cik=cik,
        symbol=symbol,
        name=name,
        exchange=exchange,
    )


def make_existing_company(
    cik="0000320193",
    symbol="AAPL",
    name="Old Company",
):
    company = Company(
        cik=cik,
        name=name,
        sector="Technology",
        industry="Old Industry",
        country="United States",
        website="https://old.example.com",
        market_cap=1_000_000,
    )

    company.id = 1

    return company


def make_existing_security():
    security = Security(
        company_id=1,
        symbol="AAPL",
        exchange="NYSE",
    )

    security.id = 10

    return security


def make_service():
    db = Mock()

    service = UniverseService.__new__(
        UniverseService
    )

    service.db = db
    service.provider = Mock()
    service.company_repo = Mock()
    service.security_repo = Mock()
    service.provenance_repo = Mock()
    service.identifier_history_repo = Mock()
    service.security_repo.get_by_company_ids.return_value = []
    service.security_repo.get_active_by_exchanges.return_value = []

    return service, db


def test_sync_creates_new_company_and_security():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_ciks.return_value = []

    company = make_existing_company()

    service.company_repo.create.return_value = company

    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 1

    service.company_repo.create.assert_called_once_with(
        cik="0000320193",
        name="Apple Inc.",
        sector="",
        industry="",
        country="",
        website="",
        market_cap=None,
    )

    db.flush.assert_called_once()

    service.security_repo.create.assert_called_once_with(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    service.identifier_history_repo.upsert.assert_called_once()


def test_sync_updates_existing_company_by_cik():

    service, db = make_service()

    existing = make_existing_company()

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_ciks.return_value = [
        existing
    ]

    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 1

    assert existing.cik == "0000320193"
    assert existing.name == "Apple Inc."

    service.company_repo.create.assert_not_called()

    service.company_repo.get_by_ciks.assert_called_once()

    service.security_repo.create.assert_called_once_with(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
    )

    db.flush.assert_called_once()

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_retires_old_listing_when_exchange_changes():

    service, db = make_service()

    existing_company = make_existing_company()

    existing_security = make_existing_security()

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_ciks.return_value = [
        existing_company
    ]

    service.security_repo.get_by_company_ids.return_value = [
        existing_security
    ]
    service.security_repo.get_active_by_exchanges.return_value = [
        existing_security
    ]

    result = service.sync()

    assert result == 1

    assert existing_security.status == SecurityStatus.INACTIVE

    service.security_repo.create.assert_called_once_with(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_does_not_use_symbol_as_company_identity():

    service, db = make_service()

    existing = make_existing_company()

    service.provider.fetch.return_value = [
        make_company(
            cik="0000999999"
        )
    ]

    service.company_repo.get_by_ciks.return_value = []

    service.company_repo.create.return_value = existing

    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 1

    service.company_repo.create.assert_called_once()

    service.company_repo.get_by_ciks.assert_called_once()

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_creates_multiple_securities_for_same_cik():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company(
            cik="0000320193",
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
        make_company(
            cik="0000320193",
            symbol="AAPL-A",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
    ]

    service.company_repo.get_by_ciks.return_value = []

    company = make_existing_company()

    service.company_repo.create.return_value = company

    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 2

    service.company_repo.create.assert_called_once_with(
        cik="0000320193",
        name="Apple Inc.",
        sector="",
        industry="",
        country="",
        website="",
        market_cap=None,
    )

    assert service.security_repo.create.call_count == 2

    assert service.security_repo.create.call_args_list == [
        call(
            company_id=1,
            symbol="AAPL",
            exchange="NASDAQ",
        ),
        call(
            company_id=1,
            symbol="AAPL-A",
            exchange="NASDAQ",
        ),
    ]

    db.flush.assert_called_once()

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_deduplicates_duplicate_cik_and_symbol_records():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company(
            cik="0000320193",
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
        make_company(
            cik="0000320193",
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
    ]

    service.company_repo.get_by_ciks.return_value = []

    company = make_existing_company()

    service.company_repo.create.return_value = company

    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 1

    service.company_repo.create.assert_called_once_with(
        cik="0000320193",
        name="Apple Inc.",
        sector="",
        industry="",
        country="",
        website="",
        market_cap=None,
    )

    service.security_repo.create.assert_called_once_with(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
    )

    db.flush.assert_called_once()

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_allows_same_symbol_on_different_exchanges_for_different_companies():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company(
            cik="0000320193",
            symbol="ABC",
            name="Company A",
            exchange="NASDAQ",
        ),
        make_company(
            cik="0000999999",
            symbol="ABC",
            name="Company B",
            exchange="NYSE",
        ),
    ]

    company_a = make_existing_company(cik="0000320193", symbol="ABC", name="Company A")
    company_b = make_existing_company(cik="0000999999", symbol="ABC", name="Company B")
    company_b.id = 2
    service.company_repo.get_by_ciks.return_value = [company_a, company_b]
    service.security_repo.get_by_company_ids.return_value = []

    assert service.sync() == 2
    assert service.security_repo.create.call_count == 2
    db.commit.assert_called_once()


def test_sync_rejects_same_symbol_and_exchange_for_multiple_companies():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company(
            cik="0000320193",
            symbol="ABC",
            name="Company A",
            exchange="NASDAQ",
        ),
        make_company(
            cik="0000999999",
            symbol="ABC",
            name="Company B",
            exchange="NASDAQ",
        ),
    ]

    with pytest.raises(
        ValueError,
        match="associated with multiple companies",
    ):
        service.sync()

    service.company_repo.get_by_ciks.assert_not_called()
    service.security_repo.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_sync_marks_missing_managed_security_inactive():

    service, db = make_service()
    service.provider.fetch.return_value = [make_company()]
    service.company_repo.get_by_ciks.return_value = [make_existing_company()]

    stale = make_existing_security()
    stale.symbol = "OLD"
    stale.exchange = "NASDAQ"
    service.security_repo.get_by_company_ids.return_value = [stale]
    service.security_repo.get_active_by_exchanges.return_value = [stale]

    assert service.sync() == 1
    assert stale.status == "INACTIVE"
    db.commit.assert_called_once()


def test_sync_rolls_back_on_error():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_ciks.side_effect = (
        RuntimeError("database error")
    )

    with pytest.raises(
        RuntimeError,
        match="database error",
    ):
        service.sync()

    db.rollback.assert_called_once()
    db.commit.assert_not_called()

    service.security_repo.create.assert_not_called()


def test_sync_rejects_symbol_for_multiple_companies():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company(
            cik="0000320193",
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        ),
        make_company(
            cik="0000999999",
            symbol="AAPL",
            name="Another Company",
            exchange="NASDAQ",
        ),
    ]

    with pytest.raises(
        ValueError,
        match="associated with multiple companies",
    ):
        service.sync()

    service.company_repo.get_by_ciks.assert_not_called()

    service.company_repo.create.assert_not_called()

    service.security_repo.get_by_company_ids.assert_not_called()

    service.security_repo.create.assert_not_called()

    # Validation happens before the transaction scope.
    db.commit.assert_not_called()
    db.rollback.assert_not_called()

def test_sync_records_sec_provenance_for_company_identity_and_security():

    service, db = make_service()

    service.provider.fetch.return_value = [make_company()]
    service.company_repo.get_by_ciks.return_value = []

    company = make_existing_company()
    service.company_repo.create.return_value = company
    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 1

    fields = [
        call.kwargs["field_name"]
        for call in service.provenance_repo.upsert.call_args_list
    ]

    assert fields == [
        CompanyField.CIK,
        CompanyField.NAME,
    ]

    security = service.security_repo.create.return_value
    assert security.source == DataSource.SEC
    assert security.fetched_at is not None
