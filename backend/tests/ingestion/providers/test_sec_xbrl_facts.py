from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
import requests

from quantcore.core.exceptions import DataValidationError, ExternalDataError, InvalidInputError
from quantcore.ingestion.providers.sec import SECProvider
from quantcore.schemas.sec_xbrl_fact import SECXBRLFactObservationData


def make_response(payload):
    response = Mock()
    response.json.return_value = payload
    return response


def test_get_sec_xbrl_fact_observations_preserves_revisions_and_taxonomies():
    payload = {
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "label": "Revenue",
                    "units": {
                        "USD": [
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "val": 391000000000,
                                "accn": "0000320193-24-000123",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-11-01",
                                "frame": "CY2024",
                                "qtrs": 4,
                                "decimals": "-6",
                            },
                            {
                                "start": "2023-10-01",
                                "end": "2024-09-28",
                                "val": 392000000000,
                                "accn": "0000320193-25-000010",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K/A",
                                "filed": "2025-02-01",
                                "frame": "CY2024",
                                "qtrs": 4,
                                "decimals": "-6",
                            },
                        ]
                    },
                }
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "end": "2024-09-28",
                                "val": 15000000000,
                                "accn": "0000320193-24-000123",
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
        return_value=make_response(payload),
    ) as mock_get:
        result = SECProvider().get_sec_xbrl_fact_observations("0000320193")

    mock_get.assert_called_once_with(
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        headers=SECProvider.HEADERS,
        timeout=30,
    )
    assert len(result) == 3
    assert all(isinstance(item, SECXBRLFactObservationData) for item in result)
    assert [item.accession_number for item in result[:2]] == [
        "0000320193-24-000123",
        "0000320193-25-000010",
    ]
    assert result[0].value == Decimal("391000000000")
    assert result[1].value == Decimal("392000000000")
    assert result[1].form == "10-K/A"
    assert result[2].taxonomy == "dei"
    assert result[2].period_start is None
    assert result[2].qtrs == 0


def test_get_sec_xbrl_fact_observations_rejects_invalid_value():
    payload = {
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "val": "not-a-number",
                                "accn": "0000320193-24-000123",
                                "form": "10-K",
                                "filed": "2024-11-01",
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=make_response(payload),
    ):
        with pytest.raises(DataValidationError, match="XBRL fact observation"):
            SECProvider().get_sec_xbrl_fact_observations("0000320193")


def test_get_sec_xbrl_fact_observations_empty_cik():
    with pytest.raises(InvalidInputError, match="CIK must not be empty"):
        SECProvider().get_sec_xbrl_fact_observations("   ")


def test_get_sec_xbrl_fact_observations_http_error():
    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=requests.RequestException("boom"),
    ):
        with pytest.raises(ExternalDataError, match="XBRL fact observations"):
            SECProvider().get_sec_xbrl_fact_observations("0000320193")
