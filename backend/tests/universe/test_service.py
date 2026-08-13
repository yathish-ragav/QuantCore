from unittest.mock import Mock

from quantcore.models.company import Company
from quantcore.models.security import Security
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


def make_existing_company():
    company = Company(
        cik="0000320193",
        symbol="OLD",
        name="Old Company",
        exchange="NYSE",
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

    return service, db


def test_sync_creates_new_company_and_security():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company()
    ]

    # Bulk company lookups return nothing.
    service.company_repo.get_by_ciks.return_value = []
    service.company_repo.get_by_symbols.return_value = []

    company = make_existing_company()

    service.company_repo.create.return_value = company

    # No existing securities.
    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 1

    service.company_repo.create.assert_called_once_with(
        cik="0000320193",
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
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


def test_sync_updates_existing_company_by_cik():

    service, db = make_service()

    existing = make_existing_company()

    service.provider.fetch.return_value = [
        make_company()
    ]

    # Company exists by CIK.
    service.company_repo.get_by_ciks.return_value = [
        existing
    ]

    service.company_repo.get_by_symbols.return_value = []

    # No existing security.
    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 1

    assert existing.cik == "0000320193"
    assert existing.symbol == "AAPL"
    assert existing.name == "Apple Inc."
    assert existing.exchange == "NASDAQ"

    service.company_repo.create.assert_not_called()

    service.company_repo.get_by_ciks.assert_called_once()
    service.company_repo.get_by_symbols.assert_called_once()

    service.security_repo.create.assert_called_once_with(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
    )

    db.flush.assert_called_once()
    db.commit.assert_called_once()


def test_sync_updates_existing_security():

    service, db = make_service()

    existing_company = make_existing_company()
    existing_security = make_existing_security()

    service.provider.fetch.return_value = [
        make_company()
    ]

    # Existing company is found by CIK.
    service.company_repo.get_by_ciks.return_value = [
        existing_company
    ]

    service.company_repo.get_by_symbols.return_value = []

    # Existing security is already present.
    service.security_repo.get_by_company_ids.return_value = [
        existing_security
    ]

    result = service.sync()

    assert result == 1

    assert existing_security.symbol == "AAPL"
    assert existing_security.exchange == "NASDAQ"

    service.security_repo.create.assert_not_called()

    db.commit.assert_called_once()


def test_sync_falls_back_to_symbol_and_creates_security():

    service, db = make_service()

    existing = make_existing_company()

    existing.symbol = "AAPL"

    service.provider.fetch.return_value = [
        make_company()
    ]

    # No company with the incoming CIK.
    service.company_repo.get_by_ciks.return_value = []

    # Existing company is found through symbol.
    service.company_repo.get_by_symbols.return_value = [
        existing
    ]

    # No existing security.
    service.security_repo.get_by_company_ids.return_value = []

    result = service.sync()

    assert result == 1

    assert existing.cik == "0000320193"
    assert existing.symbol == "AAPL"
    assert existing.name == "Apple Inc."
    assert existing.exchange == "NASDAQ"

    service.company_repo.create.assert_not_called()

    service.security_repo.create.assert_called_once_with(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
    )

    db.commit.assert_called_once()


def test_sync_does_not_create_duplicate_security():

    service, db = make_service()

    existing_company = make_existing_company()
    existing_security = make_existing_security()

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_ciks.return_value = [
        existing_company
    ]

    service.company_repo.get_by_symbols.return_value = []

    service.security_repo.get_by_company_ids.return_value = [
        existing_security
    ]

    result = service.sync()

    assert result == 1

    service.security_repo.create.assert_not_called()

    assert existing_security.symbol == "AAPL"
    assert existing_security.exchange == "NASDAQ"

    db.commit.assert_called_once()


def test_sync_rolls_back_on_error():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company()
    ]

    # Force the new bulk lookup to fail.
    service.company_repo.get_by_ciks.side_effect = (
        RuntimeError("database error")
    )

    try:
        service.sync()
        assert False
    except RuntimeError as exc:
        assert str(exc) == "database error"

    db.rollback.assert_called_once()
    db.commit.assert_not_called()

    service.security_repo.create.assert_not_called()