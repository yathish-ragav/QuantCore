from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.enums import FinancialStatementType
from quantcore.schemas.balance_sheet import BalanceSheetData
from quantcore.services.balance_sheet_service import BalanceSheetService


def make_company():
    company = Mock()
    company.id = 1
    return company


def make_security(company):
    security = Mock()
    security.id = 10
    security.company_id = company.id
    security.symbol = "AAPL"
    security.company = company
    return security


def make_statement(fiscal_date):
    return BalanceSheetData(
        fiscal_date=fiscal_date,
        cash_and_cash_equivalents=100,
        short_term_investments=50,
        accounts_receivable=75,
        inventory=125,
        total_current_assets=500,
        property_plant_equipment_net=300,
        goodwill=20,
        intangible_assets=30,
        total_assets=1000,
        accounts_payable=80,
        short_term_debt=100,
        total_current_liabilities=250,
        long_term_debt=300,
        total_liabilities=550,
        total_equity=450,
        retained_earnings=250,
        total_debt=400,
        net_debt=300,
        working_capital=250,
    )


def make_service():
    db = Mock()
    service = BalanceSheetService.__new__(BalanceSheetService)
    service.db = db
    service.provider = Mock()
    service.provider.SOURCE = "FMP"
    service.security_repo = Mock()
    service.statement_repo = Mock()
    service.revision_repo = Mock()
    return service, db


def test_get_balance_sheets():
    service, _ = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    statements = [Mock(), Mock()]
    service.statement_repo.get_for_company.return_value = statements

    assert service.get_balance_sheets("AAPL") == statements
    service.statement_repo.get_for_company.assert_called_once_with(company.id)


def test_get_balance_sheets_company_not_found():
    service, _ = make_service()
    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(ValueError, match="Company not found: AAPL"):
        service.get_balance_sheets("AAPL")


def test_sync_balance_sheets_creates_new_statements():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_balance_sheets.return_value = [
        make_statement(date(2024, 9, 28)),
        make_statement(date(2023, 9, 30)),
    ]
    service.statement_repo.get_by_company_and_date.return_value = None

    result = service.sync_balance_sheets("AAPL")

    assert result.created == 2
    assert result.updated == 0
    assert result.unchanged == 0
    assert result.records_processed == 2
    assert service.statement_repo.create.call_count == 2
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_balance_sheets_skips_existing():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_balance_sheets.return_value = [
        make_statement(date(2024, 9, 28))
    ]
    service.statement_repo.get_by_company_and_date.return_value = make_statement(date(2024, 9, 28))

    result = service.sync_balance_sheets("AAPL")
    assert result.created == 0
    assert result.updated == 0
    assert result.unchanged == 1
    assert result.records_processed == 1
    service.statement_repo.create.assert_not_called()
    db.commit.assert_called_once()


def test_sync_balance_sheets_rolls_back_on_provider_error():
    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    service.provider.get_balance_sheets.side_effect = RuntimeError("provider error")

    with pytest.raises(RuntimeError, match="provider error"):
        service.sync_balance_sheets("AAPL")

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sync_balance_sheets_rejects_empty_symbol():
    service, db = make_service()

    with pytest.raises(ValueError, match="Symbol must not be empty"):
        service.sync_balance_sheets("   ")

    service.provider.get_balance_sheets.assert_not_called()
    service.statement_repo.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_get_balance_sheets_supports_as_of():
    service, _ = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    revision = Mock()
    service.revision_repo.get_latest_for_company_as_of.return_value = [revision]

    result = service.get_balance_sheets(
        "AAPL",
        as_of=datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc),
    )

    assert result == [revision]
    service.revision_repo.get_latest_for_company_as_of.assert_called_once()


def test_sync_balance_sheets_updates_changed_observation_and_creates_revision():
    from types import SimpleNamespace

    service, db = make_service()
    company = make_company()
    service.security_repo.get_by_symbol.return_value = make_security(company)
    incoming = make_statement(date(2024, 9, 28))
    existing = SimpleNamespace(**incoming.model_dump(), id=42, company_id=company.id, source_reference=None)
    existing.total_assets = 900.0
    service.provider.get_balance_sheets.return_value = [incoming]
    service.statement_repo.get_by_company_and_date.return_value = existing
    service.revision_repo.get_next_revision_number.return_value = 2

    result = service.sync_balance_sheets("AAPL")

    assert result.created == 0
    assert result.updated == 1
    assert result.unchanged == 0
    assert result.records_processed == 1
    assert existing.total_assets == 1000.0
    service.revision_repo.create.assert_called_once()
    db.commit.assert_called_once()
