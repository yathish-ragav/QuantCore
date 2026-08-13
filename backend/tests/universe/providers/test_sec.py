from unittest.mock import Mock, patch

from quantcore.universe.providers.sec import (
    SECUniverseProvider,
)


def make_response(data):
    response = Mock()

    response.raise_for_status.return_value = None

    response.json.return_value = {
        "fields": [
            "cik",
            "name",
            "ticker",
            "exchange",
        ],
        "data": data,
    }

    return response


@patch(
    "quantcore.universe.providers.sec.requests.get"
)
def test_sec_universe_fetch(mock_get):

    mock_get.return_value = make_response(
        [
            [
                320193,
                "Apple Inc.",
                "AAPL",
                "Nasdaq",
            ],
            [
                789019,
                "Microsoft Corporation",
                "MSFT",
                "Nasdaq",
            ],
        ]
    )

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

    mock_get.return_value = make_response(
        [
            [
                320193,
                "Apple Inc.",
                "AAPL",
                "Nasdaq",
            ],
            [
                None,
                "Invalid Company",
                "BAD",
                "NASDAQ",
            ],
            [
                123456,
                "",
                "BAD2",
                "NYSE",
            ],
            [
                123456,
                "Invalid Row",
                "",
                "NYSE",
            ],
        ]
    )

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


@patch(
    "quantcore.universe.providers.sec.requests.get"
)
def test_sec_universe_rejects_unexpected_schema(
    mock_get,
):

    response = Mock()

    response.raise_for_status.return_value = None

    response.json.return_value = {
        "fields": [
            "ticker",
            "cik",
        ],
        "data": [],
    }

    mock_get.return_value = response

    provider = SECUniverseProvider()

    try:
        provider.fetch()
        assert False
    except ValueError as exc:
        assert str(exc) == (
            "Unexpected SEC universe schema."
        )