from datetime import date

import pytest
import requests
from unittest.mock import Mock, patch

from quantcore.core.exceptions import (
    ExternalDataError,
    InvalidInputError,
)
from quantcore.ingestion.providers.sec import SECProvider
from quantcore.schemas.cash_flow_statement import CashFlowStatementData
from quantcore.schemas.income_statement import IncomeStatementData


@pytest.fixture(autouse=True)
def reset_sec_ticker_cache():
    """
    Reset the SEC ticker cache before and after every test.
    """

    SECProvider._ticker_to_cik = None

    yield

    SECProvider._ticker_to_cik = None


# ---------------------------------------------------------------------------
# Ticker map
# ---------------------------------------------------------------------------


def test_sec_load_ticker_map_success():

    fake_response = Mock()

    fake_response.json.return_value = {
        "0": {
            "cik_str": 320193,
            "ticker": "AAPL",
            "title": "Apple Inc.",
        },
        "1": {
            "cik_str": 789019,
            "ticker": "MSFT",
            "title": "Microsoft Corporation",
        },
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ) as mock_get:

        result = SECProvider()._load_ticker_map()

    mock_get.assert_called_once_with(
        SECProvider.TICKER_URL,
        headers=SECProvider.HEADERS,
        timeout=30,
    )

    fake_response.raise_for_status.assert_called_once_with()

    assert result == {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
    }


def test_sec_load_ticker_map_is_cached():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get"
    ) as mock_get:

        result = SECProvider()._load_ticker_map()

    mock_get.assert_not_called()

    assert result == {
        "AAPL": "0000320193",
    }


def test_sec_get_cik_success():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    result = SECProvider()._get_cik("aapl")

    assert result == "0000320193"


def test_sec_get_cik_missing_ticker():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    with pytest.raises(ValueError) as exc_info:
        SECProvider()._get_cik("MSFT")

    assert str(exc_info.value) == (
        "SEC CIK not found for ticker: MSFT"
    )


def test_sec_ticker_map_http_error():

    fake_response = Mock()

    fake_response.raise_for_status.side_effect = requests.HTTPError(
        "500 Server Error"
    )

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ):

        with pytest.raises(ExternalDataError) as exc_info:
            SECProvider()._load_ticker_map()

    assert str(exc_info.value) == (
        "Failed to retrieve SEC ticker mapping."
    )


# ---------------------------------------------------------------------------
# Income statement retrieval
# ---------------------------------------------------------------------------


def test_sec_get_income_statements_success():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    fake_response = Mock()

    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "val": 391035000000,
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2024,
                                "filed": "2024-11-01",
                                "accn": "0000320193-24-000123",
                            }
                        ]
                    }
                },
                "GrossProfit": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "val": 180683000000,
                                "form": "10-K",
                                "fp": "FY",
                                "filed": "2024-11-01",
                            }
                        ]
                    }
                },
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "val": 123216000000,
                                "form": "10-K",
                                "fp": "FY",
                                "filed": "2024-11-01",
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "val": 93736000000,
                                "form": "10-K",
                                "fp": "FY",
                                "filed": "2024-11-01",
                            }
                        ]
                    }
                },
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD-per-shares": [
                            {
                                "end": "2024-09-28",
                                "val": 6.08,
                                "form": "10-K",
                                "fp": "FY",
                                "filed": "2024-11-01",
                            }
                        ]
                    }
                },
                "WeightedAverageNumberOfDilutedSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "end": "2024-09-28",
                                "val": 15408095000,
                                "form": "10-K",
                                "fp": "FY",
                                "filed": "2024-11-01",
                            }
                        ]
                    }
                },
            }
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ) as mock_get:

        result = SECProvider().get_income_statements("AAPL")

    mock_get.assert_called_once_with(
        (
            "https://data.sec.gov/"
            "api/xbrl/companyfacts/"
            "CIK0000320193.json"
        ),
        headers=SECProvider.HEADERS,
        timeout=30,
    )

    fake_response.raise_for_status.assert_called_once_with()

    assert len(result) == 1
    assert isinstance(result[0], IncomeStatementData)

    assert result[0].fiscal_date == date(2024, 9, 28)
    assert result[0].total_revenue == 391035000000
    assert result[0].period_start == date(2023, 10, 1)
    assert result[0].fiscal_year == 2024
    assert result[0].fiscal_period == "FY"
    assert result[0].filing_date == date(2024, 11, 1)
    assert result[0].filing_form == "10-K"
    assert result[0].accession_number == "0000320193-24-000123"
    assert result[0].gross_profit == 180683000000
    assert result[0].operating_income == 123216000000
    assert result[0].net_income == 93736000000
    assert result[0].eps == 6.08
    assert result[0].shares_outstanding == 15408095000


def test_sec_get_income_statements_empty_symbol():

    with pytest.raises(InvalidInputError) as exc_info:
        SECProvider().get_income_statements("   ")

    assert str(exc_info.value) == (
        "Symbol must not be empty."
    )


def test_sec_http_error():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    fake_response = Mock()

    fake_response.raise_for_status.side_effect = requests.HTTPError(
        "500 Server Error"
    )

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ):

        with pytest.raises(ExternalDataError) as exc_info:
            SECProvider().get_income_statements("AAPL")

    assert str(exc_info.value) == (
        "Failed to retrieve income statement data from SEC."
    )


def test_sec_timeout():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=requests.Timeout("Request timed out"),
    ):

        with pytest.raises(ExternalDataError) as exc_info:
            SECProvider().get_income_statements("AAPL")

    assert str(exc_info.value) == (
        "Failed to retrieve income statement data from SEC."
    )


# ---------------------------------------------------------------------------
# XBRL fact helpers
# ---------------------------------------------------------------------------


def test_sec_get_fact_prefers_requested_unit():

    us_gaap = {
        "Revenue": {
            "units": {
                "USD": [
                    {
                        "val": 100,
                    }
                ],
                "EUR": [
                    {
                        "val": 90,
                    }
                ],
            }
        }
    }

    result = SECProvider._get_fact(
        us_gaap,
        ["Revenue"],
        preferred_unit="USD",
    )

    assert result == [
        {
            "val": 100,
        }
    ]


def test_sec_get_fact_falls_back_to_first_available_unit():

    us_gaap = {
        "Revenue": {
            "units": {
                "EUR": [
                    {
                        "val": 90,
                    }
                ]
            }
        }
    }

    result = SECProvider._get_fact(
        us_gaap,
        ["Revenue"],
        preferred_unit="USD",
    )

    assert result == [
        {
            "val": 90,
        }
    ]


def test_sec_get_fact_returns_empty_when_missing():

    us_gaap = {}

    result = SECProvider._get_fact(
        us_gaap,
        ["Revenue"],
        preferred_unit="USD",
    )

    assert result == []


# ---------------------------------------------------------------------------
# Annual fact filtering
# ---------------------------------------------------------------------------


def test_sec_is_annual_fact():

    annual_fact = {
        "form": "10-K",
        "fp": "FY",
    }

    amended_annual_fact = {
        "form": "10-K/A",
        "fp": "FY",
    }

    quarterly_fact = {
        "form": "10-Q",
        "fp": "Q1",
    }

    assert SECProvider._is_annual_fact(
        annual_fact
    ) is True

    assert SECProvider._is_annual_fact(
        amended_annual_fact
    ) is True

    assert SECProvider._is_annual_fact(
        quarterly_fact
    ) is False


def test_sec_get_fiscal_dates():

    facts = [
        {
            "end": "2024-09-28",
            "form": "10-K",
            "fp": "FY",
        },
        {
            "end": "2023-09-30",
            "form": "10-K",
            "fp": "FY",
        },
        {
            "end": "2024-06-29",
            "form": "10-Q",
            "fp": "Q3",
        },
        {
            "end": "2024-09-28",
            "form": "10-K",
            "fp": "FY",
        },
    ]

    result = SECProvider._get_fiscal_dates(
        facts
    )

    assert result == [
        date(2023, 9, 30),
        date(2024, 9, 28),
    ]


# ---------------------------------------------------------------------------
# Value extraction
# ---------------------------------------------------------------------------


def test_sec_value_on_date_uses_latest_filing():

    facts = [
        {
            "end": "2024-09-28",
            "val": 100,
            "form": "10-K",
            "fp": "FY",
            "filed": "2024-11-01",
        },
        {
            "end": "2024-09-28",
            "val": 110,
            "form": "10-K/A",
            "fp": "FY",
            "filed": "2025-01-15",
        },
    ]

    result = SECProvider._value_on_date(
        facts,
        date(2024, 9, 28),
    )

    assert result == 110.0


def test_sec_value_on_date_returns_none_when_missing():

    facts = [
        {
            "end": "2023-09-30",
            "val": 100,
            "form": "10-K",
            "fp": "FY",
            "filed": "2023-11-01",
        }
    ]

    result = SECProvider._value_on_date(
        facts,
        date(2024, 9, 28),
    )

    assert result is None


def test_sec_integer_value_on_date():

    facts = [
        {
            "end": "2024-09-28",
            "val": 15408095000.9,
            "form": "10-K",
            "fp": "FY",
            "filed": "2024-11-01",
        }
    ]

    result = SECProvider._integer_value_on_date(
        facts,
        date(2024, 9, 28),
    )

    assert result == 15408095000


def test_sec_integer_value_on_date_returns_none_when_missing():

    result = SECProvider._integer_value_on_date(
        [],
        date(2024, 9, 28),
    )

    assert result is None

# ---------------------------------------------------------------------------
# Cash flow statements
# ---------------------------------------------------------------------------


def test_sec_get_cash_flow_statements_success():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    fake_response = Mock()

    def annual_fact(value):
        return {
            "units": {
                "USD": [
                    {
                        "start": "2023-10-01",
                        "end": "2024-09-28",
                        "val": value,
                        "form": "10-K",
                        "fp": "FY",
                        "fy": 2024,
                        "filed": "2024-11-01",
                        "accn": "0000320193-24-000123",
                    }
                ]
            }
        }

    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": (
                    annual_fact(118254000000)
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": (
                    annual_fact(9500000000)
                ),
                "NetCashProvidedByUsedInInvestingActivities": (
                    annual_fact(3700000000)
                ),
                "NetCashProvidedByUsedInFinancingActivities": (
                    annual_fact(-121000000000)
                ),
                "DepreciationDepletionAndAmortization": (
                    annual_fact(11400000000)
                ),
                "ShareBasedCompensation": (
                    annual_fact(11700000000)
                ),
                "PaymentsOfDividends": (
                    annual_fact(15200000000)
                ),
                "PaymentsForRepurchaseOfCommonStock": (
                    annual_fact(95000000000)
                ),
                "CashAndCashEquivalentsPeriodIncreaseDecrease": (
                    annual_fact(700000000)
                ),
            }
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ) as mock_get:

        result = SECProvider().get_cash_flow_statements("AAPL")

    mock_get.assert_called_once_with(
        (
            "https://data.sec.gov/"
            "api/xbrl/companyfacts/"
            "CIK0000320193.json"
        ),
        headers=SECProvider.HEADERS,
        timeout=30,
    )

    assert len(result) == 1
    assert isinstance(result[0], CashFlowStatementData)

    assert result[0].fiscal_date == date(2024, 9, 28)
    assert result[0].period_start == date(2023, 10, 1)
    assert result[0].fiscal_year == 2024
    assert result[0].fiscal_period == "FY"
    assert result[0].filing_date == date(2024, 11, 1)
    assert result[0].filing_form == "10-K"
    assert result[0].accession_number == "0000320193-24-000123"
    assert result[0].operating_cash_flow == 118254000000
    assert result[0].capital_expenditure == 9500000000

    # Free cash flow is derived as operating cash flow minus
    # capital expenditure, using SEC's positive-outflow convention.
    assert result[0].free_cash_flow == (
        118254000000 - 9500000000
    )

    assert result[0].investing_cash_flow == 3700000000
    assert result[0].financing_cash_flow == -121000000000
    assert result[0].depreciation_and_amortization == 11400000000
    assert result[0].stock_based_compensation == 11700000000
    assert result[0].dividends_paid == 15200000000
    assert result[0].share_repurchases == 95000000000
    assert result[0].net_change_in_cash == 700000000


def test_sec_get_cash_flow_statements_empty_symbol():

    with pytest.raises(
        InvalidInputError,
        match="Symbol must not be empty",
    ):
        SECProvider().get_cash_flow_statements("")


def test_sec_get_cash_flow_statements_missing_facts_returns_none_fields():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    fake_response = Mock()

    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "val": 100000000,
                                "form": "10-K",
                                "fp": "FY",
                                "filed": "2024-11-01",
                            }
                        ]
                    }
                },
            }
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ):
        result = SECProvider().get_cash_flow_statements("AAPL")

    assert len(result) == 1
    assert result[0].operating_cash_flow == 100000000
    assert result[0].capital_expenditure is None

    # Free cash flow cannot be derived without capital expenditure.
    assert result[0].free_cash_flow is None


def test_sec_cash_flow_http_error():

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=requests.exceptions.HTTPError(),
    ):
        with pytest.raises(ExternalDataError):
            SECProvider().get_cash_flow_statements("AAPL")
