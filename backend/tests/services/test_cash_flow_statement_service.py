from datetime import date
from unittest.mock import Mock

import pytest

from quantcore.schemas.cash_flow_statement import (
    CashFlowStatementData,
)
from quantcore.services.cash_flow_statement_service import (
    CashFlowStatementService,
)


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


def make_statement(
    fiscal_date,
    operating_cash_flow=1000.0,
):

    return CashFlowStatementData(
        fiscal_date=fiscal_date,
        operating_cash_flow=operating_cash_flow,
        capital_expenditure=-200.0,
        free_cash_flow=800.0,
        investing_cash_flow=-150.0,
        financing_cash_flow=-500.0,
        depreciation_and_amortization=100.0,
        stock_based_compensation=90.0,
        dividends_paid=-60.0,
        share_repurchases=-400.0,
        net_change_in_cash=350.0,
    )


def make_service():

    db = Mock()

    service = CashFlowStatementService.__new__(
        CashFlowStatementService
    )

    service.db = db
    service.provider = Mock()
    service.provider.SOURCE = "FMP"
    service.security_repo = Mock()
    service.statement_repo = Mock()

    return service, db


def test_get_cash_flow_statements_returns_statements():

    service, db = make_service()

    company = make_company()

    statements = [Mock(), Mock()]

    service.security_repo.get_by_symbol.return_value = (
        make_security(company)
    )

    service.statement_repo.get_for_company.return_value = (
        statements
    )

    result = service.get_cash_flow_statements("AAPL")

    assert result == statements

    service.statement_repo.get_for_company.assert_called_once_with(
        company.id
    )


def test_get_cash_flow_statements_company_not_found():

    service, db = make_service()

    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="Company not found: AAPL",
    ):
        service.get_cash_flow_statements("AAPL")

    service.statement_repo.get_for_company.assert_not_called()


def test_sync_cash_flow_statements_creates_new_statements():

    service, db = make_service()

    company = make_company()

    statements = [
        make_statement(
            date(
                2024,
                9,
                28,
            )
        ),
        make_statement(
            date(
                2023,
                9,
                30,
            )
        ),
    ]

    service.security_repo.get_by_symbol.return_value = (
        make_security(company)
    )

    service.provider.get_cash_flow_statements.return_value = (
        statements
    )

    service.statement_repo.get_by_company_and_date.return_value = (
        None
    )

    result = service.sync_cash_flow_statements(
        "AAPL"
    )

    assert len(result) == 2

    assert (
        service.statement_repo
        .create.call_count
        == 2
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_cash_flow_statements_skips_existing():

    service, db = make_service()

    company = make_company()

    service.security_repo.get_by_symbol.return_value = (
        make_security(company)
    )

    service.provider.get_cash_flow_statements.return_value = [
        make_statement(
            date(
                2024,
                9,
                28,
            )
        ),
    ]

    service.statement_repo.get_by_company_and_date.return_value = (
        Mock()
    )

    result = service.sync_cash_flow_statements(
        "AAPL"
    )

    assert result == []

    service.statement_repo.create.assert_not_called()

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_cash_flow_statements_company_not_found():

    service, db = make_service()

    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="Company not found: AAPL",
    ):
        service.sync_cash_flow_statements("AAPL")

    service.provider.get_cash_flow_statements.assert_not_called()

    service.statement_repo.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_cash_flow_statements_rolls_back_on_provider_error():

    service, db = make_service()

    company = make_company()

    service.security_repo.get_by_symbol.return_value = (
        make_security(company)
    )

    service.provider.get_cash_flow_statements.side_effect = (
        RuntimeError("provider error")
    )

    with pytest.raises(
        RuntimeError,
        match="provider error",
    ):
        service.sync_cash_flow_statements("AAPL")

    service.statement_repo.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_cash_flow_statements_rolls_back_on_repository_lookup_error():

    service, db = make_service()

    company = make_company()

    service.security_repo.get_by_symbol.return_value = (
        make_security(company)
    )

    service.provider.get_cash_flow_statements.return_value = [
        make_statement(
            date(
                2024,
                9,
                28,
            )
        ),
    ]

    service.statement_repo.get_by_company_and_date.side_effect = (
        RuntimeError("database lookup error")
    )

    with pytest.raises(
        RuntimeError,
        match="database lookup error",
    ):
        service.sync_cash_flow_statements("AAPL")

    service.statement_repo.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_cash_flow_statements_rolls_back_on_repository_create_error():

    service, db = make_service()

    company = make_company()

    service.security_repo.get_by_symbol.return_value = (
        make_security(company)
    )

    service.provider.get_cash_flow_statements.return_value = [
        make_statement(
            date(
                2024,
                9,
                28,
            )
        ),
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
        service.sync_cash_flow_statements("AAPL")

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_cash_flow_statements_rejects_empty_symbol():

    service, db = make_service()

    with pytest.raises(
        ValueError,
        match="Symbol must not be empty.",
    ):
        service.sync_cash_flow_statements("   ")

    service.security_repo.get_by_symbol.assert_not_called()

    service.provider.get_cash_flow_statements.assert_not_called()

    service.statement_repo.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
