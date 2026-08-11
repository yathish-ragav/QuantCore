from datetime import date
from unittest.mock import Mock, patch

import pytest

from quantcore.ingestion.providers.sec import SECProvider


def test_sec_get_cik():

    provider = SECProvider()

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    assert provider._get_cik("AAPL") == "0000320193"


def test_sec_get_cik_case_insensitive():

    provider = SECProvider()

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    assert provider._get_cik("aapl") == "0000320193"


def test_sec_unknown_ticker():

    provider = SECProvider()

    SECProvider._ticker_to_cik = {
        "AAPL": "0000320193",
    }

    with pytest.raises(ValueError):
        provider._get_cik("NOTAREALCOMPANY")


@patch(
    "quantcore.ingestion.providers.sec.requests.get"
)
def test_sec_load_ticker_map(mock_get):

    mock_response = Mock()

    mock_response.raise_for_status.return_value = None

    mock_response.json.return_value = {
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

    mock_get.return_value = mock_response

    SECProvider._ticker_to_cik = None

    provider = SECProvider()

    mapping = provider._load_ticker_map()

    assert mapping["AAPL"] == "0000320193"
    assert mapping["MSFT"] == "0000789019"


@patch(
    "quantcore.ingestion.providers.sec.requests.get"
)
def test_sec_income_statements(mock_get):

    ticker_response = Mock()

    ticker_response.raise_for_status.return_value = None

    ticker_response.json.return_value = {
        "0": {
            "cik_str": 320193,
            "ticker": "AAPL",
            "title": "Apple Inc.",
        }
    }

    companyfacts_response = Mock()

    companyfacts_response.raise_for_status.return_value = None

    companyfacts_response.json.return_value = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "val": 391035000000,
                                "form": "10-K",
                                "fp": "FY",
                                "filed": "2024-11-01",
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
            }
        }
    }

    mock_get.side_effect = [
        ticker_response,
        companyfacts_response,
    ]

    SECProvider._ticker_to_cik = None

    provider = SECProvider()

    result = provider.get_income_statements("AAPL")

    assert len(result) == 1

    statement = result[0]

    assert statement.fiscal_date == date(2024, 9, 28)

    assert statement.total_revenue == 391035000000

    assert statement.gross_profit == 180683000000

    assert statement.operating_income == 123216000000

    assert statement.net_income == 93736000000


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
    ]

    dates = SECProvider._get_fiscal_dates(facts)

    assert dates == [
        date(2023, 9, 30),
        date(2024, 9, 28),
    ]


def test_sec_ignores_quarterly_facts():

    facts = [
        {
            "end": "2024-06-29",
            "val": 100,
            "form": "10-Q",
            "fp": "Q3",
        }
    ]

    value = SECProvider._value_on_date(
        facts,
        date(2024, 6, 29),
    )

    assert value is None


def test_sec_latest_filing_wins():

    facts = [
        {
            "end": "2024-09-28",
            "val": 390000000000,
            "form": "10-K",
            "fp": "FY",
            "filed": "2024-10-01",
        },
        {
            "end": "2024-09-28",
            "val": 391035000000,
            "form": "10-K/A",
            "fp": "FY",
            "filed": "2024-11-01",
        },
    ]

    value = SECProvider._value_on_date(
        facts,
        date(2024, 9, 28),
    )

    assert value == 391035000000