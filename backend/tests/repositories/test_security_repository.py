from unittest.mock import Mock

from quantcore.models.security import Security
from quantcore.repositories.security_repository import (
    SecurityRepository,
)


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

    db.query.assert_called_once_with(Security)

    query.filter.assert_called_once()

    filtered_query.first.assert_called_once()

    assert result == security


def test_get_by_symbol_returns_none():

    repository, db = make_repository()

    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = None

    result = repository.get_by_symbol("UNKNOWN")

    assert result is None


def test_get_by_company_and_symbol_returns_security():

    repository, db = make_repository()

    security = Mock(spec=Security)

    query = db.query.return_value
    filtered_query = query.filter.return_value
    filtered_query.first.return_value = security

    result = repository.get_by_company_and_symbol(
        company_id=1,
        symbol="AAPL",
    )

    db.query.assert_called_once_with(Security)

    query.filter.assert_called_once()

    filtered_query.first.assert_called_once()

    assert result == security


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