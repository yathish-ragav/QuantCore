from datetime import date
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def make_statement(
    fiscal_date=date(2024, 9, 28),
    operating_cash_flow=118254000000.0,
    capital_expenditure=-9500000000.0,
    free_cash_flow=108754000000.0,
    investing_cash_flow=3700000000.0,
    financing_cash_flow=-121000000000.0,
    depreciation_and_amortization=11400000000.0,
    stock_based_compensation=11700000000.0,
    dividends_paid=-15200000000.0,
    share_repurchases=-95000000000.0,
    net_change_in_cash=700000000.0,
):
    statement = Mock()

    statement.fiscal_date = fiscal_date
    statement.operating_cash_flow = operating_cash_flow
    statement.capital_expenditure = capital_expenditure
    statement.free_cash_flow = free_cash_flow
    statement.investing_cash_flow = investing_cash_flow
    statement.financing_cash_flow = financing_cash_flow
    statement.depreciation_and_amortization = (
        depreciation_and_amortization
    )
    statement.stock_based_compensation = (
        stock_based_compensation
    )
    statement.dividends_paid = dividends_paid
    statement.share_repurchases = share_repurchases
    statement.net_change_in_cash = net_change_in_cash

    return statement


def test_get_cash_flow_statements_returns_statements():
    statement = make_statement()

    with patch(
        "quantcore.api.dependencies.CashFlowStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_cash_flow_statements.return_value = [
            statement
        ]

        response = client.get(
            "/cash-flow-statements/AAPL"
        )

    assert response.status_code == 200

    assert response.json() == [
        {
            "fiscal_date": "2024-09-28",
            "operating_cash_flow": 118254000000.0,
            "capital_expenditure": -9500000000.0,
            "free_cash_flow": 108754000000.0,
            "investing_cash_flow": 3700000000.0,
            "financing_cash_flow": -121000000000.0,
            "depreciation_and_amortization": 11400000000.0,
            "stock_based_compensation": 11700000000.0,
            "dividends_paid": -15200000000.0,
            "share_repurchases": -95000000000.0,
            "net_change_in_cash": 700000000.0,
        }
    ]

    service.get_cash_flow_statements.assert_called_once_with(
        "AAPL"
    )

    service.sync_cash_flow_statements.assert_not_called()


def test_get_cash_flow_statements_returns_empty_list():
    with patch(
        "quantcore.api.dependencies.CashFlowStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_cash_flow_statements.return_value = []

        response = client.get(
            "/cash-flow-statements/AAPL"
        )

    assert response.status_code == 200

    assert response.json() == []


def test_get_cash_flow_statements_normalizes_lowercase_symbol():
    with patch(
        "quantcore.api.dependencies.CashFlowStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.get_cash_flow_statements.return_value = []

        response = client.get(
            "/cash-flow-statements/aapl"
        )

    assert response.status_code == 200

    service.get_cash_flow_statements.assert_called_once_with(
        "AAPL"
    )


def test_sync_cash_flow_statements_returns_statements_added():
    with patch(
        "quantcore.api.dependencies.CashFlowStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_cash_flow_statements.return_value = [
            Mock(),
            Mock(),
        ]

        response = client.post(
            "/cash-flow-statements/AAPL/sync"
        )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "statements_added": 2,
    }

    service.sync_cash_flow_statements.assert_called_once_with(
        "AAPL"
    )


def test_sync_cash_flow_statements_returns_zero_when_none_added():
    with patch(
        "quantcore.api.dependencies.CashFlowStatementService"
    ) as mock_service_class:

        service = Mock()

        mock_service_class.return_value = service

        service.sync_cash_flow_statements.return_value = []

        response = client.post(
            "/cash-flow-statements/AAPL/sync"
        )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "statements_added": 0,
    }
