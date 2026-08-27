from datetime import date
from unittest.mock import Mock, patch

import pytest
import requests

from quantcore.core.exceptions import ExternalDataError, InvalidInputError
from quantcore.ingestion.providers.sec import SECProvider
from quantcore.schemas.balance_sheet import BalanceSheetData


def annual_fact(value):
    return {
        "units": {
            "USD": [
                {
                    "end": "2024-09-28",
                    "val": value,
                    "form": "10-K",
                    "fp": "FY",
                    "filed": "2024-11-01",
                    "fy": 2024,
                    "accn": "0000320193-24-000123",
                }
            ]
        }
    }


def test_sec_balance_sheet_success():
    SECProvider._ticker_to_cik = {"AAPL": "0000320193"}

    response = Mock()
    response.json.return_value = {
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": annual_fact(5000),
                "ShortTermInvestments": annual_fact(1000),
                "AccountsReceivableNetCurrent": annual_fact(2000),
                "InventoryNet": annual_fact(3000),
                "AssetsCurrent": annual_fact(12000),
                "PropertyPlantAndEquipmentNet": annual_fact(8000),
                "Goodwill": annual_fact(500),
                "FiniteLivedIntangibleAssetsNet": annual_fact(300),
                "Assets": annual_fact(25000),
                "AccountsPayableCurrent": annual_fact(1800),
                "ShortTermDebtCurrent": annual_fact(700),
                "LiabilitiesCurrent": annual_fact(6000),
                "LongTermDebtNoncurrent": annual_fact(5000),
                "Liabilities": annual_fact(14000),
                "StockholdersEquity": annual_fact(11000),
                "RetainedEarningsAccumulatedDeficit": annual_fact(7000),
            }
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=response,
    ) as mock_get:
        result = SECProvider().get_balance_sheets("AAPL")

    mock_get.assert_called_once_with(
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        headers=SECProvider.HEADERS,
        timeout=30,
    )

    assert len(result) == 1
    assert isinstance(result[0], BalanceSheetData)
    assert result[0].fiscal_date == date(2024, 9, 28)
    assert result[0].total_assets == 25000
    assert result[0].total_debt == 5700
    assert result[0].net_debt == 700
    assert result[0].working_capital == 6000
    assert result[0].period_type.value == "INSTANT"
    assert result[0].fiscal_year == 2024
    assert result[0].filing_date.isoformat() == "2024-11-01"
    assert result[0].filing_form == "10-K"
    assert result[0].accession_number == "0000320193-24-000123"


def test_sec_balance_sheet_missing_fields_are_none():
    SECProvider._ticker_to_cik = {"AAPL": "0000320193"}

    response = Mock()
    response.json.return_value = {
        "facts": {
            "us-gaap": {
                "Assets": annual_fact(1000),
            }
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=response,
    ):
        result = SECProvider().get_balance_sheets("AAPL")

    assert len(result) == 1
    assert result[0].total_assets == 1000
    assert result[0].cash_and_cash_equivalents is None
    assert result[0].total_debt is None


def test_sec_balance_sheet_empty_symbol():
    with pytest.raises(
        InvalidInputError,
        match="Symbol must not be empty",
    ):
        SECProvider().get_balance_sheets("")


def test_sec_balance_sheet_http_error():
    SECProvider._ticker_to_cik = {"AAPL": "0000320193"}

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=requests.HTTPError(),
    ):
        with pytest.raises(ExternalDataError):
            SECProvider().get_balance_sheets("AAPL")
