from datetime import date
from unittest.mock import Mock

from quantcore.models.income_statement import IncomeStatement
from quantcore.repositories.income_statement_repository import (
    IncomeStatementRepository,
)


def make_repository():

    db = Mock()

    repository = IncomeStatementRepository(db)

    return repository, db


def test_get_by_company_and_date_returns_statement():

    repository, db = make_repository()

    statement = Mock(
        spec=IncomeStatement
    )

    db.scalar.return_value = statement

    result = repository.get_by_company_and_date(
        company_id=1,
        fiscal_date=date(
            2024,
            9,
            28,
        ),
    )

    db.scalar.assert_called_once()

    assert result == statement

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_by_company_and_date_returns_none():

    repository, db = make_repository()

    db.scalar.return_value = None

    result = repository.get_by_company_and_date(
        company_id=1,
        fiscal_date=date(
            2024,
            9,
            28,
        ),
    )

    db.scalar.assert_called_once()

    assert result is None

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_create_income_statement():

    repository, db = make_repository()

    statement = repository.create(
        company_id=1,
        fiscal_date=date(
            2024,
            9,
            28,
        ),
        total_revenue=394_000_000_000,
        gross_profit=175_000_000_000,
        operating_income=119_000_000_000,
        net_income=99_000_000_000,
        eps=6.4,
        shares_outstanding=15_000_000_000,
    )

    db.add.assert_called_once_with(
        statement
    )

    assert isinstance(
        statement,
        IncomeStatement,
    )

    assert statement.company_id == 1
    assert statement.fiscal_date == date(
        2024,
        9,
        28,
    )
    assert statement.total_revenue == (
        394_000_000_000
    )
    assert statement.gross_profit == (
        175_000_000_000
    )
    assert statement.operating_income == (
        119_000_000_000
    )
    assert statement.net_income == (
        99_000_000_000
    )
    assert statement.eps == 6.4
    assert statement.shares_outstanding == (
        15_000_000_000
    )

    # Repository must not control the transaction.
    db.commit.assert_not_called()
    db.rollback.assert_not_called()