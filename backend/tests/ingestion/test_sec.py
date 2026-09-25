from datetime import date

import pytest
import requests
from unittest.mock import Mock, patch

from quantcore.core.enums import FinancialPeriodType
from quantcore.core.exceptions import (
    DataValidationError,
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



def test_sec_uses_injected_http_session():
    session = Mock(spec=requests.Session)
    response = Mock()
    session.get.return_value = response
    provider = SECProvider(http_session=session)

    provider._get(
        "https://data.sec.gov/test",
        headers=SECProvider.HEADERS,
        timeout=30,
    )

    session.get.assert_called_once_with(
        "https://data.sec.gov/test",
        headers=SECProvider.HEADERS,
        timeout=30,
    )


def test_sec_http_session_is_shared_by_sqlalchemy_session():
    db = Mock()
    db.info = {}

    first = SECProvider.http_session_for_session(db)
    second = SECProvider.http_session_for_session(db)

    assert first is second
    assert isinstance(first, requests.Session)

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
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "end": "2024-09-28",
                                "val": 15000000000,
                                "form": "10-K",
                                "filed": "2024-11-01",
                            }
                        ]
                    }
                }
            },
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
    assert result[0].shares_outstanding == 15000000000
    assert result[0].weighted_average_shares_outstanding == 15408095000


def test_sec_income_statement_dates_ignore_instant_share_facts():
    """Instant share facts must not create synthetic income-statement periods."""
    SECProvider._ticker_to_cik = {"TEST": "0001234567"}

    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2024-01-01",
                                "end": "2024-12-31",
                                "val": 100,
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2024,
                                "filed": "2025-03-01",
                                "accn": "0001234567-25-000001",
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2024-01-01",
                                "end": "2024-12-31",
                                "val": 80,
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2024,
                                "filed": "2025-03-01",
                                "accn": "0001234567-25-000001",
                            }
                        ]
                    }
                },
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "end": "2024-12-31",
                                "val": 1000,
                                "form": "10-K",
                                "filed": "2025-03-01",
                                "accn": "0001234567-25-000001",
                            },
                            {
                                "end": "2025-03-15",
                                "val": 1010,
                                "form": "10-K",
                                "filed": "2025-03-15",
                                "accn": "0001234567-25-000002",
                            },
                        ]
                    }
                }
            },
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ):
        result = SECProvider().get_income_statements("TEST")

    assert len(result) == 1
    assert result[0].fiscal_date == date(2024, 12, 31)
    assert result[0].period_start == date(2024, 1, 1)
    assert result[0].filing_date == date(2025, 3, 1)
    assert result[0].accession_number == "0001234567-25-000001"
    assert result[0].shares_outstanding == 1000


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


def test_sec_quarterly_fact_requires_standalone_qtrs_one():
    standalone = {
        "start": "2026-01-01",
        "end": "2026-03-31",
        "form": "10-Q",
        "fp": "Q1",
        "qtrs": 1,
    }
    ytd = {**standalone, "end": "2026-06-30", "qtrs": 2, "fp": "Q2"}
    amended = {**standalone, "form": "10-Q/A"}

    assert SECProvider._is_quarterly_fact(standalone) is True
    assert SECProvider._is_quarterly_fact(amended) is True
    assert SECProvider._is_quarterly_fact(ytd) is False


def test_sec_instant_fact_accepts_quarter_end_10q():
    fact = {
        "end": "2026-06-30",
        "form": "10-Q",
        "fp": "Q2",
        "qtrs": 0,
    }

    assert SECProvider._is_instant_fact(fact) is True


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

def test_sec_get_quarterly_income_statements_selects_standalone_fact():
    SECProvider._ticker_to_cik = {"TEST": "0001234567"}
    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01", "end": "2026-03-31", "val": 100,
                                "form": "10-Q", "fp": "Q1", "qtrs": 1, "fy": 2026,
                                "filed": "2026-05-01", "accn": "0001234567-26-000001",
                            },
                            {
                                "start": "2026-01-01", "end": "2026-06-30", "val": 230,
                                "form": "10-Q", "fp": "Q2", "qtrs": 2, "fy": 2026,
                                "filed": "2026-08-01", "accn": "0001234567-26-000002",
                            },
                            {
                                "start": "2026-04-01", "end": "2026-06-30", "val": 130,
                                "form": "10-Q", "fp": "Q2", "qtrs": 1, "fy": 2026,
                                "filed": "2026-08-01", "accn": "0001234567-26-000002",
                            },
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01", "end": "2026-03-31", "val": 20,
                                "form": "10-Q", "fp": "Q1", "qtrs": 1, "fy": 2026,
                                "filed": "2026-05-01", "accn": "0001234567-26-000001",
                            },
                            {
                                "start": "2026-04-01", "end": "2026-06-30", "val": 25,
                                "form": "10-Q", "fp": "Q2", "qtrs": 1, "fy": 2026,
                                "filed": "2026-08-01", "accn": "0001234567-26-000002",
                            },
                        ]
                    }
                },
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {"end": "2026-06-30", "val": 1000, "form": "10-Q", "fp": "Q2", "qtrs": 0, "filed": "2026-08-01", "accn": "0001234567-26-000002"}
                        ]
                    }
                }
            },
        }
    }

    with patch("quantcore.ingestion.providers.sec.requests.get", return_value=fake_response):
        result = SECProvider().get_quarterly_income_statements("TEST")

    assert [(row.fiscal_date, row.total_revenue, row.net_income) for row in result] == [
        (date(2026, 3, 31), 100.0, 20.0),
        (date(2026, 6, 30), 130.0, 25.0),
    ]
    assert result[-1].shares_outstanding == 1000
    assert result[-1].period_type.value == "QUARTERLY"


def test_sec_get_balance_sheets_includes_quarter_end_instant_facts():
    SECProvider._ticker_to_cik = {"TEST": "0001234567"}
    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {"end": "2025-12-31", "val": 1000, "form": "10-K", "fp": "FY", "qtrs": 0, "filed": "2026-03-01"},
                            {"end": "2026-06-30", "val": 1100, "form": "10-Q", "fp": "Q2", "qtrs": 0, "filed": "2026-08-01"},
                        ]
                    }
                },
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            {"end": "2026-06-30", "val": 300, "form": "10-Q", "fp": "Q2", "qtrs": 0, "filed": "2026-08-01"},
                        ]
                    }
                },
            }
        }
    }

    with patch("quantcore.ingestion.providers.sec.requests.get", return_value=fake_response):
        result = SECProvider().get_balance_sheets("TEST")

    assert [row.fiscal_date for row in result] == [date(2025, 12, 31), date(2026, 6, 30)]
    assert result[-1].period_type is FinancialPeriodType.INSTANT
    assert result[-1].total_assets == 1100.0


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


def test_sec_get_income_statements_does_not_require_revenue_anchor():
    """Valid SEC income facts must survive when revenue concepts are absent."""
    SECProvider._ticker_to_cik = {"AARD": "0001234567"}

    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": -62725000,
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-03-23",
                                "accn": "0001193125-26-119770",
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": -57591000,
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-03-23",
                                "accn": "0001193125-26-119770",
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
        result = SECProvider().get_income_statements("AARD")

    assert len(result) == 1
    assert result[0].fiscal_date == date(2025, 12, 31)
    assert result[0].total_revenue is None
    assert result[0].operating_income == -62725000
    assert result[0].net_income == -57591000
    assert result[0].filing_date == date(2026, 3, 23)
    assert result[0].accession_number == "0001193125-26-119770"


def test_sec_get_cash_flow_statements_does_not_require_operating_cash_flow_anchor():
    """Valid annual cash-flow facts must survive when OCF is absent."""
    SECProvider._ticker_to_cik = {"TEST": "0001234567"}

    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInInvestingActivities": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-12-31",
                                "val": -1000000,
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-03-23",
                                "accn": "0001234567-26-000001",
                            }
                        ]
                    }
                },
                "NetCashProvidedByUsedInFinancingActivities": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-12-31",
                                "val": 500000,
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-03-23",
                                "accn": "0001234567-26-000001",
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
        result = SECProvider().get_cash_flow_statements("TEST")

    assert len(result) == 1
    assert result[0].fiscal_date == date(2025, 12, 31)
    assert result[0].operating_cash_flow is None
    assert result[0].investing_cash_flow == -1000000
    assert result[0].financing_cash_flow == 500000
    assert result[0].filing_date == date(2026, 3, 23)
    assert result[0].accession_number == "0001234567-26-000001"


def test_sec_xbrl_rejects_period_ending_after_filing_date():
    SECProvider._ticker_to_cik = {"AAL": "0000000001"}

    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2027-07-17",
                                "val": 100,
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2026,
                                "filed": "2026-07-23",
                                "accn": "0000000001-26-000001",
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ):
        with pytest.raises(DataValidationError, match="period_end"):
            SECProvider().get_sec_xbrl_fact_observations("0000000001")


@pytest.mark.parametrize("annual_form", ["20-F", "20-F/A", "40-F", "40-F/A", "10-KT", "10-KT/A"])
def test_sec_annual_financial_facts_support_non_10k_annual_forms(annual_form):
    """Annual US-listed foreign/transition filers must not be dropped by form filtering."""
    SECProvider._ticker_to_cik = {"TEST": "0001234567"}

    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": 1000000,
                                "form": annual_form,
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-03-01",
                                "accn": "0001234567-26-000001",
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=fake_response,
    ):
        result = SECProvider().get_income_statements("TEST")

    assert len(result) == 1
    assert result[0].fiscal_date == date(2025, 12, 31)
    assert result[0].total_revenue == 1000000
    assert result[0].filing_form == annual_form


def test_sec_get_income_statements_falls_back_to_ifrs_full_for_40f():
    """IFRS 40-F issuers must populate normalized income statements."""
    SECProvider._ticker_to_cik = {"AAUC": "0001993344"}

    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "ifrs-full": {
                "RevenueFromContractsWithCustomers": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": 1331824000,
                                "form": "40-F",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-04-01",
                                "accn": "0001628280-26-022512",
                            }
                        ]
                    }
                },
                "ProfitLossAttributableToOwnersOfParent": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": -51847000,
                                "form": "40-F",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-04-01",
                                "accn": "0001628280-26-022512",
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
        result = SECProvider().get_income_statements("AAUC")

    assert len(result) == 1
    assert result[0].fiscal_date == date(2025, 12, 31)
    assert result[0].total_revenue == 1331824000
    assert result[0].net_income == -51847000
    assert result[0].filing_form == "40-F"


def test_sec_get_cash_flow_statements_falls_back_to_ifrs_full_for_40f():
    """IFRS 40-F issuers must populate normalized cash-flow statements."""
    SECProvider._ticker_to_cik = {"AAUC": "0001993344"}

    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "ifrs-full": {
                "CashFlowsFromUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": 513979000,
                                "form": "40-F",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-04-01",
                                "accn": "0001628280-26-022512",
                            }
                        ]
                    }
                },
                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "val": 408136000,
                                "form": "40-F",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-04-01",
                                "accn": "0001628280-26-022512",
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
        result = SECProvider().get_cash_flow_statements("AAUC")

    assert len(result) == 1
    assert result[0].fiscal_date == date(2025, 12, 31)
    assert result[0].operating_cash_flow == 513979000
    assert result[0].capital_expenditure == 408136000
    assert result[0].free_cash_flow == 105843000


def test_sec_get_balance_sheets_falls_back_to_ifrs_full_for_40f():
    """IFRS 40-F issuers must populate normalized balance sheets."""
    SECProvider._ticker_to_cik = {"AAUC": "0001993344"}

    fake_response = Mock()
    fake_response.json.return_value = {
        "facts": {
            "ifrs-full": {
                "CashAndCashEquivalents": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-12-31",
                                "val": 479777000,
                                "form": "40-F",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-04-01",
                                "accn": "0001628280-26-022512",
                            }
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-12-31",
                                "val": 2500000000,
                                "form": "40-F",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-04-01",
                                "accn": "0001628280-26-022512",
                            }
                        ]
                    }
                },
                "Liabilities": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-12-31",
                                "val": 1500000000,
                                "form": "40-F",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-04-01",
                                "accn": "0001628280-26-022512",
                            }
                        ]
                    }
                },
                "Equity": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-12-31",
                                "val": 1000000000,
                                "form": "40-F",
                                "fp": "FY",
                                "fy": 2025,
                                "filed": "2026-04-01",
                                "accn": "0001628280-26-022512",
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
        result = SECProvider().get_balance_sheets("AAUC")

    assert len(result) == 1
    assert result[0].fiscal_date == date(2025, 12, 31)
    assert result[0].cash_and_cash_equivalents == 479777000
    assert result[0].total_assets == 2500000000
    assert result[0].total_liabilities == 1500000000
    assert result[0].total_equity == 1000000000
