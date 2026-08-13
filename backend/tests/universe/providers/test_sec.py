from unittest.mock import Mock, patch

from quantcore.universe.providers.sec import (
    SECUniverseProvider,
)


@patch(
    "quantcore.universe.providers.sec.requests.get"
)
def test_sec_universe_fetch(mock_get):

    response = Mock()

    response.raise_for_status.return_value = None

    response.json.return_value = {
        "0": {
            "cik": 320193,
            "name": "Apple Inc.",
            "ticker": "AAPL",
            "exchange": "Nasdaq",
        },
        "1": {
            "cik": 789019,
            "name": "Microsoft Corporation",
            "ticker": "MSFT",
            "exchange": "Nasdaq",
        },
    }

    mock_get.return_value = response

    provider = SECUniverseProvider()

    result = provider.fetch()

    assert len(result) == 2

    assert result[0].cik == "0000320193"
    assert result[0].symbol == "AAPL"
    assert result[0].name == "Apple Inc."
    assert result[0].exchange == "Nasdaq"

    assert result[1].cik == "0000789019"
    assert result[1].symbol == "MSFT"


@patch(
    "quantcore.universe.providers.sec.requests.get"
)
def test_sec_universe_skips_invalid_records(
    mock_get,
):

    response = Mock()

    response.raise_for_status.return_value = None

    response.json.return_value = {
        "0": {
            "cik": 320193,
            "name": "Apple Inc.",
            "ticker": "AAPL",
            "exchange": "Nasdaq",
        },
        "1": {
            "cik": None,
            "name": "Invalid Company",
            "ticker": "BAD",
            "exchange": "NASDAQ",
        },
        "2": {
            "cik": 123456,
            "name": "",
            "ticker": "BAD2",
            "exchange": "NYSE",
        },
    }

    mock_get.return_value = response

    provider = SECUniverseProvider()

    result = provider.fetch()

    assert len(result) == 1
    assert result[0].symbol == "AAPL"


@patch(
    "quantcore.universe.providers.sec.requests.get"
)
def test_sec_universe_http_error(mock_get):

    response = Mock()

    response.raise_for_status.side_effect = (
        RuntimeError("SEC request failed")
    )

    mock_get.return_value = response

    provider = SECUniverseProvider()

    try:
        provider.fetch()
        assert False
    except RuntimeError as exc:
        assert str(exc) == "SEC request failed"