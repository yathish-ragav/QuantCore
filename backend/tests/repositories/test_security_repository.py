from unittest.mock import Mock

from quantcore.models.security import Security
from quantcore.repositories.security_repository import SecurityRepository


def make_repository():

    db = Mock()

    repository = SecurityRepository(db)

    return repository, db


def test_get_by_symbol_returns_security():

    repository, db = make_repository()

    security = Mock(
        spec=Security
    )

    db.scalar.return_value = security

    result = repository.get_by_symbol(
        "AAPL"
    )

    assert result == security

    db.scalar.assert_called_once()

    db.query.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_symbol_returns_none_when_not_found():

    repository, db = make_repository()

    db.scalar.return_value = None

    result = repository.get_by_symbol(
        "UNKNOWN"
    )

    assert result is None

    db.scalar.assert_called_once()

    db.query.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_symbols_returns_securities():

    repository, db = make_repository()

    securities = [
        Mock(
            spec=Security
        )
    ]

    db.scalars.return_value.all.return_value = (
        securities
    )

    result = repository.get_by_symbols(
        ["AAPL"]
    )

    assert result == securities

    db.scalars.assert_called_once()

    db.scalars.return_value.all.assert_called_once()

    db.query.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_symbols_returns_empty_for_empty_input():

    repository, db = make_repository()

    result = repository.get_by_symbols([])

    assert result == []

    db.scalar.assert_not_called()
    db.scalars.assert_not_called()
    db.query.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_company_and_symbol_returns_security():

    repository, db = make_repository()

    security = Mock(
        spec=Security
    )

    db.scalar.return_value = security

    result = repository.get_by_company_and_symbol(
        1,
        "AAPL",
    )

    assert result == security

    db.scalar.assert_called_once()

    db.query.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_company_and_symbol_returns_none_when_not_found():

    repository, db = make_repository()

    db.scalar.return_value = None

    result = repository.get_by_company_and_symbol(
        1,
        "UNKNOWN",
    )

    assert result is None

    db.scalar.assert_called_once()

    db.query.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_company_ids_returns_securities():

    repository, db = make_repository()

    securities = [
        Mock(
            spec=Security
        )
    ]

    db.scalars.return_value.all.return_value = (
        securities
    )

    result = repository.get_by_company_ids(
        [1]
    )

    assert result == securities

    db.scalars.assert_called_once()

    db.scalars.return_value.all.assert_called_once()

    db.query.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_company_ids_returns_empty_for_empty_input():

    repository, db = make_repository()

    result = repository.get_by_company_ids([])

    assert result == []

    db.scalar.assert_not_called()
    db.scalars.assert_not_called()
    db.query.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_create_security():

    repository, db = make_repository()

    security = repository.create(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
    )

    db.add.assert_called_once_with(
        security
    )

    assert isinstance(
        security,
        Security,
    )

    assert security.company_id == 1
    assert security.symbol == "AAPL"
    assert security.exchange == "NASDAQ"

    # Repository must not control the transaction.
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.refresh.assert_not_called()