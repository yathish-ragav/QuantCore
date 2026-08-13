from unittest.mock import Mock

from quantcore.models.company import Company
from quantcore.repositories.company_repository import CompanyRepository


def make_repository():
    db = Mock()
    repository = CompanyRepository(db)

    return repository, db


def test_get_by_symbol_returns_company():

    repository, db = make_repository()

    company = Mock(spec=Company)

    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = company

    result = repository.get_by_symbol("AAPL")

    db.query.assert_called_once_with(Company)

    query.filter.assert_called_once()

    filtered_query.first.assert_called_once()

    assert result == company


def test_get_by_symbol_returns_none_when_not_found():

    repository, db = make_repository()

    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = None

    result = repository.get_by_symbol("UNKNOWN")

    assert result is None


def test_get_by_cik_returns_company():

    repository, db = make_repository()

    company = Mock(spec=Company)

    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = company

    result = repository.get_by_cik(
        "0000320193"
    )

    db.query.assert_called_once_with(Company)

    query.filter.assert_called_once()

    filtered_query.first.assert_called_once()

    assert result == company


def test_create_company():

    repository, db = make_repository()

    company = repository.create(
        cik="0000320193",
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        website="https://www.apple.com",
        market_cap=3_000_000_000_000,
        exchange="NASDAQ",
    )

    db.add.assert_called_once_with(company)

    assert isinstance(company, Company)

    assert company.cik == "0000320193"
    assert company.symbol == "AAPL"
    assert company.name == "Apple Inc."
    assert company.exchange == "NASDAQ"
    assert company.sector == "Technology"
    assert company.industry == "Consumer Electronics"
    assert company.country == "United States"
    assert company.website == "https://www.apple.com"
    assert company.market_cap == 3_000_000_000_000

    # Repository must not control the transaction.
    db.commit.assert_not_called()
    db.refresh.assert_not_called()


def test_update_company():

    repository, db = make_repository()

    company = Company(
        cik="0000320193",
        symbol="AAPL",
        name="Old Apple",
        exchange="NASDAQ",
        sector="Old Sector",
        industry="Old Industry",
        country="Old Country",
        website="https://old.apple.com",
        market_cap=1_000_000,
    )

    result = repository.update(
        company=company,
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        website="https://www.apple.com",
        market_cap=3_000_000_000_000,
        cik="0000320193",
        exchange="NASDAQ",
    )

    assert result is company

    assert company.cik == "0000320193"
    assert company.symbol == "AAPL"
    assert company.name == "Apple Inc."
    assert company.exchange == "NASDAQ"
    assert company.sector == "Technology"
    assert company.industry == "Consumer Electronics"
    assert company.country == "United States"
    assert company.website == "https://www.apple.com"
    assert company.market_cap == 3_000_000_000_000

    # Repository must not control the transaction.
    db.commit.assert_not_called()
    db.refresh.assert_not_called()