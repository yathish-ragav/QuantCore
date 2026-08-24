from unittest.mock import Mock, patch

import pytest
import requests

from quantcore.core.exceptions import ExternalDataError
from quantcore.ingestion.providers.fmp import FMPClient
from quantcore.schemas.balance_sheet import BalanceSheetData


def test_fmp_balance_sheet_success():
    response = Mock()
    response.json.return_value = [
        {
            "date": "2025-09-27",
            "cashAndCashEquivalents": 5000,
            "shortTermInvestments": 1000,
            "accountsReceivables": 2000,
            "inventory": 3000,
            "totalCurrentAssets": 12000,
            "propertyPlantEquipmentNet": 8000,
            "goodwill": 500,
            "intangibleAssets": 300,
            "totalAssets": 25000,
            "accountPayables": 1800,
            "shortTermDebt": 700,
            "totalCurrentLiabilities": 6000,
            "longTermDebt": 5000,
            "totalLiabilities": 14000,
            "totalStockholdersEquity": 11000,
            "retainedEarnings": 7000,
            "totalDebt": 5700,
            "netDebt": 700,
            "workingCapital": 6000,
        }
    ]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ) as mock_get:
        result = FMPClient().get_balance_sheets("AAPL", limit=10)

    response.raise_for_status.assert_called_once()
    mock_get.assert_called_once_with(
        "https://financialmodelingprep.com/stable/balance-sheet-statement",
        params={
            "symbol": "AAPL",
            "limit": 10,
            "apikey": FMPClient().api_key,
        },
        timeout=30,
    )

    assert len(result) == 1
    assert isinstance(result[0], BalanceSheetData)
    assert result[0].total_assets == 25000
    assert result[0].total_equity == 11000
    assert result[0].total_debt == 5700


def test_fmp_balance_sheet_derives_debt_and_working_capital():
    response = Mock()
    response.json.return_value = [
        {
            "date": "2025-09-27",
            "cashAndCashEquivalents": 100,
            "shortTermDebt": 200,
            "longTermDebt": 800,
            "totalCurrentAssets": 1000,
            "totalCurrentLiabilities": 700,
        }
    ]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ):
        result = FMPClient().get_balance_sheets("AAPL")

    assert result[0].total_debt == 1000
    assert result[0].net_debt == 900
    assert result[0].working_capital == 300


def test_fmp_balance_sheet_empty_response():
    response = Mock()
    response.json.return_value = []

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ):
        assert FMPClient().get_balance_sheets("AAPL") == []


def test_fmp_balance_sheet_http_error():
    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        side_effect=requests.HTTPError(),
    ):
        with pytest.raises(ExternalDataError):
            FMPClient().get_balance_sheets("AAPL")


def test_fmp_balance_sheet_invalid_shape():
    response = Mock()
    response.json.return_value = {"error": "invalid"}

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ):
        with pytest.raises(ValueError, match="must be a list"):
            FMPClient().get_balance_sheets("AAPL")


def test_fmp_balance_sheet_empty_symbol():
    with pytest.raises(ValueError, match="Symbol must not be empty"):
        FMPClient().get_balance_sheets("")


def test_fmp_balance_sheet_invalid_limit():
    with pytest.raises(ValueError, match="Limit must be greater than zero"):
        FMPClient().get_balance_sheets("AAPL", limit=0)

def test_fmp_balance_sheet_accepts_provider_field_aliases():
    response = Mock()
    response.json.return_value = [
        {
            "date": "2025-09-27",
            "accountReceivables": 200,
            "accountPayables": 150,
        }
    ]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ):
        result = FMPClient().get_balance_sheets("AAPL")

    assert result[0].accounts_receivable == 200
    assert result[0].accounts_payable == 150
