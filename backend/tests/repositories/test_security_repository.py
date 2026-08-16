from unittest.mock import Mock

from quantcore.models.security import Security
from quantcore.repositories.security_repository import SecurityRepository


def make_repository():
    db = Mock()
    repository = SecurityRepository(db)
    return repository, db


def test_get_by_symbol_returns_security():
    repository, db = make_repository()

    security = Mock(spec=Security)
    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = security

    result = repository.get_by_symbol("AAPL")

    assert result == security
    db.query.assert_called_once_with(Security)
    query.filter.assert_called_once()
    filtered_query.first.assert_called_once()


def test_get_by_symbols_returns_securities():
    repository, db = make_repository()

    securities = [Mock(spec=Security)]
    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.all.return_value = securities

    result = repository.get_by_symbols(["AAPL"])

    assert result == securities
    db.query.assert_called_once_with(Security)
    query.filter.assert_called_once()


def test_get_by_symbols_returns_empty_for_empty_input():
    repository, db = make_repository()

    assert repository.get_by_symbols([]) == []
    db.query.assert_not_called()


def test_get_by_company_and_symbol_returns_security():
    repository, db = make_repository()

    security = Mock(spec=Security)
    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = security

    result = repository.get_by_company_and_symbol(1, "AAPL")

    assert result == security
    query.filter.assert_called_once()


def test_get_by_company_ids_returns_securities():
    repository, db = make_repository()

    securities = [Mock(spec=Security)]
    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.all.return_value = securities

    result = repository.get_by_company_ids([1])

    assert result == securities


def test_create_security():
    repository, db = make_repository()

    security = repository.create(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
    )

    db.add.assert_called_once_with(security)
    assert isinstance(security, Security)
    assert security.company_id == 1
    assert security.symbol == "AAPL"
    assert security.exchange == "NASDAQ"
    db.commit.assert_not_called()
