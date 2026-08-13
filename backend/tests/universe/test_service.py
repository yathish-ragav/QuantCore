from unittest.mock import Mock

from quantcore.models.company import Company
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
    return Company(
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


def make_service():

    db = Mock()

    service = UniverseService.__new__(
        UniverseService
    )

    service.db = db
    service.provider = Mock()
    service.company_repo = Mock()

    return service, db


def test_sync_creates_new_company():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_cik.return_value = None
    service.company_repo.get_by_symbol.return_value = None

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

    db.commit.assert_called_once()


def test_sync_updates_existing_company_by_cik():

    service, db = make_service()

    existing = make_existing_company()

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_cik.return_value = existing

    result = service.sync()

    assert result == 1

    assert existing.cik == "0000320193"
    assert existing.symbol == "AAPL"
    assert existing.name == "Apple Inc."
    assert existing.exchange == "NASDAQ"

    service.company_repo.create.assert_not_called()
    service.company_repo.get_by_symbol.assert_not_called()

    db.commit.assert_called_once()


def test_sync_falls_back_to_symbol():

    service, db = make_service()

    existing = make_existing_company()
    existing.symbol = "AAPL"

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_cik.return_value = None
    service.company_repo.get_by_symbol.return_value = existing

    result = service.sync()

    assert result == 1

    assert existing.cik == "0000320193"
    assert existing.symbol == "AAPL"
    assert existing.name == "Apple Inc."
    assert existing.exchange == "NASDAQ"

    service.company_repo.create.assert_not_called()

    db.commit.assert_called_once()


def test_sync_rolls_back_on_error():

    service, db = make_service()

    service.provider.fetch.return_value = [
        make_company()
    ]

    service.company_repo.get_by_cik.side_effect = (
        RuntimeError("database error")
    )

    try:
        service.sync()
        assert False
    except RuntimeError as exc:
        assert str(exc) == "database error"

    db.rollback.assert_called_once()
    db.commit.assert_not_called()