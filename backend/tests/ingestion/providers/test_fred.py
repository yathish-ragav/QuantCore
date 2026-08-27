from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from quantcore.core.exceptions import DataValidationError, ExternalDataError, InvalidInputError
from quantcore.ingestion.providers.fred import FREDClient


def client():
    with patch("quantcore.ingestion.providers.fred.settings.FRED_API_KEY", "test-key"):
        return FREDClient()


def test_get_series_normalizes_metadata():
    provider = client()
    provider._get = lambda path, params: {
        "seriess": [{
            "id": "GDP",
            "title": "Gross Domestic Product",
            "frequency": "Quarterly",
            "frequency_short": "Q",
            "units": "Billions of Dollars",
            "units_short": "Bil. of $",
            "seasonal_adjustment": "Seasonally Adjusted",
            "seasonal_adjustment_short": "SA",
            "observation_start": "1947-01-01",
            "observation_end": "2026-04-01",
            "last_updated": "2026-07-30 08:00:00-05:00",
            "notes": "test",
        }]
    }

    result = provider.get_series("gdp")

    assert result.series_id == "GDP"
    assert result.frequency_short == "Q"
    assert result.observation_start == date(1947, 1, 1)


def test_get_observations_preserves_requested_vintage_and_missing_values():
    provider = client()
    provider._get = lambda path, params: {
        "realtime_start": "2020-02-01",
        "realtime_end": "2020-02-01",
        "observations": [
            {
                "date": "2020-01-01",
                "value": "100.25",
                "realtime_start": "2020-02-01",
                "realtime_end": "9999-12-31",
            },
            {
                "date": "2020-02-01",
                "value": ".",
                "realtime_start": "2020-02-01",
                "realtime_end": "9999-12-31",
            },
        ],
    }

    result = provider.get_observations("GDP", vintage_date=date(2020, 2, 1))

    assert result[0].value == Decimal("100.25")
    assert result[0].vintage_date == date(2020, 2, 1)
    assert result[1].value is None


def test_get_series_rejects_invalid_payload():
    provider = client()
    provider._get = lambda path, params: {"seriess": []}

    with pytest.raises(DataValidationError):
        provider.get_series("GDP")


def test_get_observations_translates_request_failure():
    provider = client()
    with patch(
        "quantcore.ingestion.providers.fred.requests.get",
        side_effect=__import__("requests").RequestException("network"),
    ):
        with pytest.raises(ExternalDataError):
            provider.get_observations("GDP")


def test_get_observations_preserves_row_level_realtime_period():
    provider = client()
    provider._get = lambda path, params: {
        "observations": [{
            "date": "2020-01-01",
            "value": "100",
            "realtime_start": "2020-02-01",
            "realtime_end": "2020-02-29",
        }],
    }

    result = provider.get_observations("GDP", vintage_date=date(2020, 2, 15))

    assert result[0].realtime_start == date(2020, 2, 1)
    assert result[0].realtime_end == date(2020, 2, 29)


def test_get_observations_rejects_row_not_covering_requested_vintage():
    provider = client()
    provider._get = lambda path, params: {
        "observations": [{
            "date": "2020-01-01",
            "value": "100",
            "realtime_start": "2020-03-01",
            "realtime_end": "9999-12-31",
        }],
    }

    with pytest.raises(DataValidationError):
        provider.get_observations("GDP", vintage_date=date(2020, 2, 15))


def test_get_observations_rejects_future_vintage():
    provider = client()
    with pytest.raises(InvalidInputError):
        provider.get_observations("GDP", vintage_date=date(2999, 1, 1))
