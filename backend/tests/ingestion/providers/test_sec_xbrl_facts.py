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


def test_companyfacts_cache_is_instance_scoped_and_reused():
    payload = {"facts": {"us-gaap": {}}}
    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=make_response(payload),
    ) as mock_get:
        provider = SECProvider()
        assert provider._get_company_facts(
            "0000320193", error_message="boom"
        ) == payload
        assert provider._get_company_facts(
            "0000320193", error_message="boom"
        ) == payload
        assert mock_get.call_count == 1

    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=make_response(payload),
    ) as mock_get:
        other_provider = SECProvider()
        assert other_provider._get_company_facts(
            "0000320193", error_message="boom"
        ) == payload
        mock_get.assert_called_once()


def test_companyfacts_cache_can_be_shared_by_financial_and_regulatory_providers():
    from quantcore.ingestion.providers.sec import SECCompanyFactsCache

    payload = {"facts": {"us-gaap": {}}}
    cache = SECCompanyFactsCache()
    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        return_value=make_response(payload),
    ) as mock_get:
        financial_provider = SECProvider(company_facts_cache=cache)
        regulatory_provider = SECProvider(company_facts_cache=cache)

        assert financial_provider._get_company_facts(
            "0000320193", error_message="boom"
        ) == payload
        assert regulatory_provider._get_company_facts(
            "0000320193", error_message="boom"
        ) == payload
        mock_get.assert_called_once()
