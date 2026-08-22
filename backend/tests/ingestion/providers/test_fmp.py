from unittest.mock import Mock, patch

import pytest
import requests

from quantcore.core.exceptions import ExternalDataError
from quantcore.ingestion.providers.fmp import FMPClient
from quantcore.schemas.cash_flow_statement import CashFlowStatementData
from quantcore.schemas.income_statement import IncomeStatementData


def test_fmp_success():
    fake_response = Mock()

    fake_response.json.return_value = [
        {
            "date": "2025-09-27",
            "revenue": 416161000000,
            "grossProfit": 195201000000,
            "operatingIncome": 123216000000,
            "netIncome": 112010000000,
            "eps": 7.46,
            "weightedAverageShsOut": 15000000000,
        }
    ]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ) as mock_get:
        result = FMPClient().get_income_statements(
            "AAPL",
            limit=10,
        )

    fake_response.raise_for_status.assert_called_once()

    mock_get.assert_called_once_with(
        "https://financialmodelingprep.com/stable/income-statement",
        params={
            "symbol": "AAPL",
            "limit": 10,
            "apikey": FMPClient().api_key,
        },
        timeout=30,
    )

    assert len(result) == 1
    assert isinstance(result[0], IncomeStatementData)

    assert result[0].fiscal_date.isoformat() == "2025-09-27"
    assert result[0].total_revenue == 416161000000
    assert result[0].gross_profit == 195201000000
    assert result[0].operating_income == 123216000000
    assert result[0].net_income == 112010000000
    assert result[0].eps == 7.46
    assert result[0].shares_outstanding == 15000000000


def test_fmp_empty_response():
    fake_response = Mock()
    fake_response.json.return_value = []

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ):
        result = FMPClient().get_income_statements("AAPL")

    assert result == []


def test_fmp_http_error():
    fake_response = Mock()

    fake_response.raise_for_status.side_effect = requests.HTTPError(
        "500 Server Error"
    )

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ):
        with pytest.raises(ExternalDataError):
            FMPClient().get_income_statements("AAPL")


def test_fmp_timeout():
    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        side_effect=requests.Timeout("Request timed out"),
    ):
        with pytest.raises(ExternalDataError):
            FMPClient().get_income_statements("AAPL")


def test_fmp_invalid_response_shape():
    fake_response = Mock()

    fake_response.json.return_value = {
        "error": "Invalid symbol"
    }

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ):
        with pytest.raises(
            ValueError,
            match="must be a list",
        ):
            FMPClient().get_income_statements("INVALID")


def test_fmp_empty_symbol():
    with pytest.raises(
        ValueError,
        match="Symbol must not be empty",
    ):
        FMPClient().get_income_statements("")


def test_fmp_invalid_limit():
    with pytest.raises(
        ValueError,
        match="Limit must be greater than zero",
    ):
        FMPClient().get_income_statements(
            "AAPL",
            limit=0,
        )


def test_fmp_multiple_statements():
    fake_response = Mock()

    fake_response.json.return_value = [
        {
            "date": "2025-09-27",
            "revenue": 1000,
            "grossProfit": 500,
            "operatingIncome": 300,
            "netIncome": 200,
            "eps": 1.5,
            "weightedAverageShsOut": 100,
        },
        {
            "date": "2024-09-28",
            "revenue": 900,
            "grossProfit": 450,
            "operatingIncome": 250,
            "netIncome": 150,
            "eps": 1.2,
            "weightedAverageShsOut": 100,
        },
    ]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ):
        result = FMPClient().get_income_statements(
            "AAPL",
            limit=2,
        )

    assert len(result) == 2
    assert result[0].total_revenue == 1000
    assert result[1].total_revenue == 900

def test_fmp_cash_flow_success():
    fake_response = Mock()

    fake_response.json.return_value = [
        {
            "date": "2025-09-27",
            "operatingCashFlow": 118254000000,
            "capitalExpenditure": -9500000000,
            "freeCashFlow": 108754000000,
            "netCashProvidedByInvestingActivities": 3700000000,
            "netCashProvidedByFinancingActivities": -121000000000,
            "depreciationAndAmortization": 11400000000,
            "stockBasedCompensation": 11700000000,
            "netDividendsPaid": -15200000000,
            "commonStockRepurchased": -95000000000,
            "netChangeInCash": 700000000,
        }
    ]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ) as mock_get:
        result = FMPClient().get_cash_flow_statements(
            "AAPL",
            limit=10,
        )

    fake_response.raise_for_status.assert_called_once()

    mock_get.assert_called_once_with(
        "https://financialmodelingprep.com/stable/cash-flow-statement",
        params={
            "symbol": "AAPL",
            "limit": 10,
            "apikey": FMPClient().api_key,
        },
        timeout=30,
    )

    assert len(result) == 1
    assert isinstance(result[0], CashFlowStatementData)

    assert result[0].fiscal_date.isoformat() == "2025-09-27"
    assert result[0].operating_cash_flow == 118254000000
    assert result[0].capital_expenditure == -9500000000
    assert result[0].free_cash_flow == 108754000000
    assert result[0].investing_cash_flow == 3700000000
    assert result[0].financing_cash_flow == -121000000000
    assert result[0].depreciation_and_amortization == 11400000000
    assert result[0].stock_based_compensation == 11700000000
    assert result[0].dividends_paid == -15200000000
    assert result[0].share_repurchases == -95000000000
    assert result[0].net_change_in_cash == 700000000


def test_fmp_cash_flow_derives_free_cash_flow_when_missing():
    fake_response = Mock()

    fake_response.json.return_value = [
        {
            "date": "2025-09-27",
            "operatingCashFlow": 100000000,
            "capitalExpenditure": -20000000,
        }
    ]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ):
        result = FMPClient().get_cash_flow_statements("AAPL")

    assert result[0].free_cash_flow == 80000000


def test_fmp_cash_flow_empty_response():
    fake_response = Mock()
    fake_response.json.return_value = []

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ):
        result = FMPClient().get_cash_flow_statements("AAPL")

    assert result == []


def test_fmp_cash_flow_http_error():
    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        side_effect=requests.exceptions.HTTPError(),
    ):
        with pytest.raises(ExternalDataError):
            FMPClient().get_cash_flow_statements("AAPL")


def test_fmp_cash_flow_timeout():
    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        side_effect=requests.exceptions.Timeout(),
    ):
        with pytest.raises(ExternalDataError):
            FMPClient().get_cash_flow_statements("AAPL")


def test_fmp_cash_flow_invalid_response_shape():
    fake_response = Mock()

    fake_response.json.return_value = {
        "error": "Invalid symbol"
    }

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ):
        with pytest.raises(
            ValueError,
            match="must be a list",
        ):
            FMPClient().get_cash_flow_statements("INVALID")


def test_fmp_cash_flow_empty_symbol():
    with pytest.raises(
        ValueError,
        match="Symbol must not be empty",
    ):
        FMPClient().get_cash_flow_statements("")


def test_fmp_cash_flow_invalid_limit():
    with pytest.raises(
        ValueError,
        match="Limit must be greater than zero",
    ):
        FMPClient().get_cash_flow_statements(
            "AAPL",
            limit=0,
        )


def test_fmp_cash_flow_multiple_statements():
    fake_response = Mock()

    fake_response.json.return_value = [
        {
            "date": "2025-09-27",
            "operatingCashFlow": 1000,
            "capitalExpenditure": -100,
        },
        {
            "date": "2024-09-28",
            "operatingCashFlow": 900,
            "capitalExpenditure": -90,
        },
    ]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=fake_response,
    ):
        result = FMPClient().get_cash_flow_statements(
            "AAPL",
            limit=2,
        )

    assert len(result) == 2
    assert result[0].operating_cash_flow == 1000
    assert result[1].operating_cash_flow == 900
