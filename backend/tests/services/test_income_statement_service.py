from datetime import date
from unittest.mock import Mock

import pytest

from quantcore.services.income_statement_service import (
    IncomeStatementService,
)


def make_company():
    company = Mock()
    company.id = 1
    company.symbol = "AAPL"
    return company


def make_statement(
    fiscal_date,
    revenue=1000.0,
):
    statement = Mock()

    statement.fiscal_date = fiscal_date
    statement.total_revenue = revenue
    statement.gross_profit = 400.0
    statement.operating_income = 200.0
    statement.net_income = 150.0
    statement.eps = 5.0
    statement.shares_outstanding = 100

    return statement


def test_sync_income_statements_creates_new_statements():

    db = Mock()

    service = IncomeStatementService.__new__(
        IncomeStatementService
    )

    service.db = db

    service.provider = Mock()
    service.company_repo = Mock()
    service.statement_repo = Mock()

    service.company_repo.get_by_symbol.return_value = (
        make_company()
    )

    service.provider.get_income_statements.return_value = [
        make_statement(date(2024, 9, 28)),
        make_statement(date(2023, 9, 30)),
    ]

    service.statement_repo.get_by_company_and_date.return_value = (
        None
    )

    result = service.sync_income_statements("AAPL")

    assert len(result) == 2

    assert (
        service.statement_repo.create.call_count
        == 2
    )

    service.statement_repo.commit.assert_called_once()


def test_sync_income_statements_skips_existing():

    db = Mock()

    service = IncomeStatementService.__new__(
        IncomeStatementService
    )

    service.db = db

    service.provider = Mock()
    service.company_repo = Mock()
    service.statement_repo = Mock()

    service.company_repo.get_by_symbol.return_value = (
        make_company()
    )

    service.provider.get_income_statements.return_value = [
        make_statement(date(2024, 9, 28)),
    ]

    service.statement_repo.get_by_company_and_date.return_value = (
        Mock()
    )

    result = service.sync_income_statements("AAPL")

    assert result == []

    service.statement_repo.create.assert_not_called()

    service.statement_repo.commit.assert_called_once()


def test_sync_income_statements_company_not_found():

    db = Mock()

    service = IncomeStatementService.__new__(
        IncomeStatementService
    )

    service.db = db

    service.provider = Mock()
    service.company_repo = Mock()
    service.statement_repo = Mock()

    service.company_repo.get_by_symbol.return_value = (
        None
    )

    with pytest.raises(
        ValueError,
        match="Company not found: AAPL",
    ):
        service.sync_income_statements("AAPL")

    service.provider.get_income_statements.assert_not_called()


def test_sync_income_statements_rolls_back_on_error():

    db = Mock()

    service = IncomeStatementService.__new__(
        IncomeStatementService
    )

    service.db = db

    service.provider = Mock()
    service.company_repo = Mock()
    service.statement_repo = Mock()

    service.company_repo.get_by_symbol.return_value = (
        make_company()
    )

    service.provider.get_income_statements.return_value = [
        make_statement(date(2024, 9, 28)),
    ]

    service.statement_repo.get_by_company_and_date.return_value = (
        None
    )

    service.statement_repo.create.side_effect = (
        RuntimeError("database error")
    )

    with pytest.raises(
        RuntimeError,
        match="database error",
    ):
        service.sync_income_statements("AAPL")

    db.rollback.assert_called_once()