from datetime import date
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def make_statement():
    statement = Mock()
    statement.period_start = None
    statement.fiscal_year = 2024
    statement.fiscal_period = "FY"
    statement.period_type = "INSTANT"
    statement.filing_date = None
    statement.filing_form = None
    statement.accession_number = None
    statement.fiscal_date = date(2024, 9, 28)
    statement.cash_and_cash_equivalents = 100.0
    statement.short_term_investments = 50.0
    statement.accounts_receivable = 75.0
    statement.inventory = 125.0
    statement.total_current_assets = 500.0
    statement.property_plant_equipment_net = 300.0
    statement.goodwill = 20.0
    statement.intangible_assets = 30.0
    statement.total_assets = 1000.0
    statement.accounts_payable = 80.0
    statement.short_term_debt = 100.0
    statement.total_current_liabilities = 250.0
    statement.long_term_debt = 300.0
    statement.total_liabilities = 550.0
    statement.total_equity = 450.0
    statement.retained_earnings = 250.0
    statement.total_debt = 400.0
    statement.net_debt = 300.0
    statement.working_capital = 250.0
    return statement


def test_get_balance_sheets():
    with patch(
        "quantcore.api.dependencies.BalanceSheetService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.get_balance_sheets.return_value = [make_statement()]

        response = client.get("/balance-sheets/AAPL")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["fiscal_date"] == "2024-09-28"
    assert body[0]["total_assets"] == 1000.0
    assert body[0]["total_debt"] == 400.0
    service.get_balance_sheets.assert_called_once_with("AAPL")


def test_get_balance_sheets_normalizes_symbol():
    with patch(
        "quantcore.api.dependencies.BalanceSheetService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.get_balance_sheets.return_value = []

        response = client.get("/balance-sheets/aapl")

    assert response.status_code == 200
    service.get_balance_sheets.assert_called_once_with("AAPL")


def test_sync_balance_sheets():
    with patch(
        "quantcore.api.dependencies.BalanceSheetService"
    ) as service_class:
        service = Mock()
        service_class.return_value = service
        service.sync_balance_sheets.return_value = [Mock(), Mock()]

        response = client.post("/balance-sheets/AAPL/sync")

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "AAPL",
        "statements_added": 2,
    }
