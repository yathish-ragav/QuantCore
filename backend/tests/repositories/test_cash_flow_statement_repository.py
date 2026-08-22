from datetime import date
from unittest.mock import Mock

from quantcore.models.cash_flow_statement import CashFlowStatement
from quantcore.repositories.cash_flow_statement_repository import (
    CashFlowStatementRepository,
)


def make_repository():

    db = Mock()

    repository = CashFlowStatementRepository(db)

    return repository, db


def test_get_by_company_and_date_returns_statement():

    repository, db = make_repository()

    statement = Mock(
        spec=CashFlowStatement
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


def test_get_for_company_returns_statements():

    repository, db = make_repository()

    statements = [
        Mock(spec=CashFlowStatement),
        Mock(spec=CashFlowStatement),
    ]

    db.scalars.return_value = statements

    result = repository.get_for_company(
        company_id=1,
    )

    db.scalars.assert_called_once()

    assert result == statements

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_for_company_returns_empty_list():

    repository, db = make_repository()

    db.scalars.return_value = []

    result = repository.get_for_company(
        company_id=1,
    )

    assert result == []


def test_create_cash_flow_statement():

    repository, db = make_repository()

    statement = repository.create(
        company_id=1,
        fiscal_date=date(
            2024,
            9,
            28,
        ),
        operating_cash_flow=118_000_000_000,
        capital_expenditure=-9_500_000_000,
        free_cash_flow=108_500_000_000,
        investing_cash_flow=3_700_000_000,
        financing_cash_flow=-121_000_000_000,
        depreciation_and_amortization=11_400_000_000,
        stock_based_compensation=11_700_000_000,
        dividends_paid=-15_200_000_000,
        share_repurchases=-95_000_000_000,
        net_change_in_cash=700_000_000,
    )

    db.add.assert_called_once_with(
        statement
    )

    assert isinstance(
        statement,
        CashFlowStatement,
    )

    assert statement.company_id == 1
    assert statement.fiscal_date == date(
        2024,
        9,
        28,
    )
    assert statement.operating_cash_flow == (
        118_000_000_000
    )
    assert statement.capital_expenditure == (
        -9_500_000_000
    )
    assert statement.free_cash_flow == (
        108_500_000_000
    )
    assert statement.investing_cash_flow == (
        3_700_000_000
    )
    assert statement.financing_cash_flow == (
        -121_000_000_000
    )
    assert statement.depreciation_and_amortization == (
        11_400_000_000
    )
    assert statement.stock_based_compensation == (
        11_700_000_000
    )
    assert statement.dividends_paid == (
        -15_200_000_000
    )
    assert statement.share_repurchases == (
        -95_000_000_000
    )
    assert statement.net_change_in_cash == (
        700_000_000
    )

    # Repository must not control the transaction.
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
