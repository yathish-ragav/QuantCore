from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from quantcore.core.exceptions import ExternalDataError, InvalidInputError
from quantcore.ingestion.providers.sec import SECProvider
from quantcore.schemas.sec_filing import SECFilingData


@pytest.fixture(autouse=True)
def reset_sec_ticker_cache():
    SECProvider._ticker_to_cik = None
    yield
    SECProvider._ticker_to_cik = None


def make_response(payload):
    response = Mock()
    response.json.return_value = payload
    return response


def test_get_sec_filings_normalizes_recent_metadata():
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-24-000123"],
                "filingDate": ["2024-11-01"],
                "reportDate": ["2024-09-28"],
                "acceptanceDateTime": ["2024-11-01T16:30:00.000Z"],
                "act": ["34"],
                "form": ["10-K"],
                "fileNumber": ["001-36743"],
                "filmNumber": ["241234567"],
                "items": [None],
                "coregistrants": [None],
                "primaryDocument": ["aapl-20240928.htm"],
                "primaryDocDescription": ["10-K"],
                "isXBRL": [1],
                "isInlineXBRL": [1],
                "isXBRL": [1],
                "fiscalYear": [2024],
                "fiscalPeriod": ["FY"],
            },
            "files": [],
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=make_response(payload),
    ) as mock_get:
        result = SECProvider().get_sec_filings("0000320193")

    mock_get.assert_called_once_with(
        "https://data.sec.gov/submissions/CIK0000320193.json",
        headers=SECProvider.HEADERS,
        timeout=30,
    )
    assert len(result) == 1
    assert isinstance(result[0], SECFilingData)
    assert result[0].accession_number == "0000320193-24-000123"
    assert result[0].filing_date == date(2024, 11, 1)
    assert result[0].report_date == date(2024, 9, 28)
    assert result[0].acceptance_datetime == datetime(
        2024, 11, 1, 16, 30, tzinfo=timezone.utc
    )
    assert result[0].form == "10-K"
    assert result[0].is_xbrl is True
    assert result[0].is_inline_xbrl is True
    assert result[0].is_amendment is False
    assert result[0].filing_url.endswith("/aapl-20240928.htm")


def test_get_sec_filings_follows_historical_submission_files():
    main = make_response(
        {
            "filings": {
                "recent": {"accessionNumber": [], "filingDate": [], "form": []},
                "files": [{"name": "CIK0000320193-submissions-001.json"}],
            }
        }
    )
    historical = make_response(
        {
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-20-000001"],
                    "filingDate": ["2020-11-01"],
                    "reportDate": ["2020-09-26"],
                    "acceptanceDateTime": ["2020-11-01T16:00:00.000Z"],
                    "form": ["10-K/A"],
                    "primaryDocument": ["aapl-20200926.htm"],
                    "primaryDocDescription": ["10-K/A"],
                    "isXBRL": [1],
                    "isInlineXBRL": [1],
                    "fiscalYear": [2020],
                    "fiscalPeriod": ["FY"],
                }
            }
        }
    )

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=[main, historical],
    ) as mock_get:
        result = SECProvider().get_sec_filings("0000320193")

    assert len(result) == 1
    assert result[0].is_amendment is True
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[1].args[0].endswith(
        "CIK0000320193-submissions-001.json"
    )


def test_get_sec_filings_empty_cik():
    with pytest.raises(InvalidInputError, match="CIK must not be empty"):
        SECProvider().get_sec_filings("   ")


def test_get_sec_filings_http_error():

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=requests.RequestException("boom"),
    ):
        with pytest.raises(ExternalDataError, match="SEC filing metadata"):
            SECProvider().get_sec_filings("0000320193")
