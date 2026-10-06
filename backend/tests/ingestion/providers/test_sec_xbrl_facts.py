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


def test_get_sec_xbrl_fact_observations_preserves_future_period_disclosed_in_filing():
    payload = {
        "facts": {
            "us-gaap": {
                "ProjectedRevenue": {
                    "units": {
                        "USD": [
                            {
                                "start": "2024-10-01",
                                "end": "2025-09-30",
                                "val": 125000000,
                                "accn": "0000320193-24-000123",
                                "form": "8-K",
                                "filed": "2024-09-23",
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
        result = SECProvider().get_sec_xbrl_fact_observations("0000320193")

    assert len(result) == 1
    assert result[0].period_end == date(2025, 9, 30)
    assert result[0].filed_at == date(2024, 9, 23)


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



def test_invalid_xbrl_observation_error_includes_safe_source_identity():
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
        with pytest.raises(DataValidationError) as exc_info:
            SECProvider().get_sec_xbrl_fact_observations("0000320193")

    message = str(exc_info.value)
    assert "taxonomy='us-gaap'" in message
    assert "concept='Revenue'" in message
    assert "unit='USD'" in message
    assert "accession='0000320193-24-000123'" in message
    assert "not-a-number" not in message


def test_get_sec_xbrl_fact_observations_rejects_non_finite_values():
    payload = {
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "val": "NaN",
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
        with pytest.raises(DataValidationError, match="value must be finite"):
            SECProvider().get_sec_xbrl_fact_observations("0000320193")

def test_get_sec_xbrl_fact_observations_empty_cik():
    with pytest.raises(InvalidInputError, match="CIK must not be empty"):
        SECProvider().get_sec_xbrl_fact_observations("   ")


def test_get_sec_xbrl_fact_observations_transport_error_is_diagnostic():
    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=requests.Timeout("boom"),
    ):
        with pytest.raises(
            ExternalDataError,
            match=r"XBRL fact observations \(transport: Timeout\)",
        ):
            SECProvider().get_sec_xbrl_fact_observations("0000320193")


def test_companyfacts_http_404_is_terminal_data_availability_failure():
    response = Mock()
    response.status_code = 404
    error = requests.HTTPError("404 Client Error", response=response)
    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=error,
    ):
        with pytest.raises(
            DataValidationError,
            match="SEC CompanyFacts is not available for this CIK",
        ):
            SECProvider().get_sec_xbrl_fact_observations("0000320193")


def test_companyfacts_404_is_cached_as_unavailable_for_shared_issuer_cache():
    response = Mock()
    response.status_code = 404
    error = requests.HTTPError("404 Client Error", response=response)
    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=error,
    ) as mock_get:
        provider = SECProvider()
        with pytest.raises(DataValidationError):
            provider._get_company_facts("0000320193", error_message="boom")
        with pytest.raises(DataValidationError):
            provider._get_company_facts("0000320193", error_message="boom")
        mock_get.assert_called_once()


def test_companyfacts_non_404_http_error_remains_retryable():
    response = Mock()
    response.status_code = 503
    error = requests.HTTPError("503 Server Error", response=response)
    with patch(
        "quantcore.ingestion.providers.sec.requests.get",
        side_effect=error,
    ):
        with pytest.raises(
            ExternalDataError,
            match=r"XBRL fact observations \(HTTP 503\)",
        ):
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

def test_get_sec_xbrl_fact_observations_normalizes_zero_fiscal_year_to_none():
    payload = {
        "facts": {
            "us-gaap": {
                "SomeConcept": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-09-28",
                                "val": 123,
                                "accn": "0000320193-24-000123",
                                "fy": 0,
                                "fp": "FY",
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
        result = SECProvider().get_sec_xbrl_fact_observations("0000320193")

    assert len(result) == 1
    assert result[0].fiscal_year is None


def test_get_sec_xbrl_fact_observations_normalizes_malformed_optional_metadata():
    payload = {
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "end": "2024-09-28",
                                "val": 123,
                                "accn": "0000320193-24-000123",
                                "fy": "not-a-year",
                                "qtrs": "not-a-quarter-count",
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
        result = SECProvider().get_sec_xbrl_fact_observations("0000320193")

    assert len(result) == 1
    assert result[0].fiscal_year is None
    assert result[0].qtrs == 0

def test_invalid_xbrl_schema_error_includes_field_and_validator_without_raw_value():
    payload = {
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "end": "2024-09-28",
                                "val": 123,
                                "accn": "0000320193-24-000123",
                                "form": "X" * 21,
                                "filed": "2024-11-01",
                                "fy": 1800,
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
        with pytest.raises(DataValidationError) as exc_info:
            SECProvider().get_sec_xbrl_fact_observations("0000320193")

    message = str(exc_info.value)
    assert "form" in message
    assert "string_too_long" in message
    assert ("X" * 21) not in message

def test_invalid_xbrl_date_error_identifies_field_without_raw_value():
    payload = {
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "units": {
                        "USD": [
                            {
                                "end": "not-a-date",
                                "val": 123,
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
        with pytest.raises(DataValidationError) as exc_info:
            SECProvider().get_sec_xbrl_fact_observations("0000320193")

    message = str(exc_info.value)
    assert "invalid period_end (ValueError)" in message
    assert "not-a-date" not in message

