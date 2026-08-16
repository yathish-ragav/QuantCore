from datetime import date
from unittest.mock import Mock

import pytest

from quantcore.schemas.income_statement import IncomeStatementData
from quantcore.services.income_statement_service import IncomeStatementService


def make_company():
    company = Mock()
    company.id = 1
    return company


def make_security(company):
    security = Mock()
    security.id = 10
    security.company_id = company.id
    security.symbol = "AAPL"
    security.exchange = "NASDAQ"
    security.company = company
    return security


def make_statement(fiscal_date, revenue=1000.0):
    return IncomeStatementData(
        fiscal_date=fiscal_date,
        total_revenue=revenue,
        gross_profit=400.0,
        operating_income=200.0,
        net_income=150.0,
        eps=5.0,
        shares_outstanding=100,
    )


def make_service():
    db = Mock()
    service = IncomeStatementService.__new__(IncomeStatementService)
    service.db = db
    service.provider = Mock()
    service.security_repo = Mock()
    service.statement_repo = Mock()
    return service, db


def test_sync_income_statements_creates_new_statements():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_income_statements.return_value = [
        make_statement(date(2024, 9, 28)),
        make_statement(date(2023, 9, 30)),
    ]
    service.statement_repo.get_by_company_and_date.return_value = None

    result = service.sync_income_statements("AAPL")

    assert len(result) == 2
    assert service.statement_repo.create.call_count == 2
    service.statement_repo.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_income_statements_skips_existing():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_income_statements.return_value = [
        make_statement(date(2024, 9, 28)),
    ]
    service.statement_repo.get_by_company_and_date.return_value = Mock()

    result = service.sync_income_statements("AAPL")

    assert result == []
    service.statement_repo.create.assert_not_called()
    service.statement_repo.commit.assert_called_once()


def test_sync_income_statements_company_not_found():
    service, db = make_service()
    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(ValueError, match="Company not found: AAPL"):
        service.sync_income_statements("AAPL")

    service.provider.get_income_statements.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_income_statements_rolls_back_on_error():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_income_statements.return_value = [
        make_statement(date(2024, 9, 28)),
    ]
    service.statement_repo.get_by_company_and_date.return_value = None
    service.statement_repo.create.side_effect = RuntimeError(
        "database error"
    )

    with pytest.raises(RuntimeError, match="database error"):
        service.sync_income_statements("AAPL")

    db.rollback.assert_called_once()
    service.statement_repo.commit.assert_not_called()
