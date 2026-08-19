from unittest.mock import Mock, patch

import pytest
import requests

from quantcore.core.exceptions import (
    DataValidationError,
    ExternalDataError,
    InvalidInputError,
)
from quantcore.ingestion.providers.fmp import FMPClient
from quantcore.schemas.quote import QuoteData


def test_fmp_quote_success():
    response = Mock()
    response.json.return_value = [{
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 200.0,
        "change": 2.0,
        "changePercentage": 1.0,
        "dayLow": 198.0,
        "dayHigh": 202.0,
        "yearLow": 150.0,
        "yearHigh": 220.0,
        "marketCap": 3000000000000,
        "priceAvg50": 195.0,
        "priceAvg200": 180.0,
        "volume": 1000000,
        "exchange": "NASDAQ",
        "open": 199.0,
        "previousClose": 198.0,
        "timestamp": 1760000000,
    }]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ) as mock_get:
        result = FMPClient().get_quote("AAPL")

    assert isinstance(result, QuoteData)
    assert result.symbol == "AAPL"
    assert result.price == 200.0
    assert result.change_percent == 1.0
    assert result.source == "fmp"
    mock_get.assert_called_once()


def test_fmp_quote_empty_symbol():
    with pytest.raises(InvalidInputError):
        FMPClient().get_quote("")


def test_fmp_quote_http_error():
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError(
        "500"
    )

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ):
        with pytest.raises(ExternalDataError):
            FMPClient().get_quote("AAPL")


def test_fmp_quote_timeout():
    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        side_effect=requests.Timeout(),
    ):
        with pytest.raises(ExternalDataError):
            FMPClient().get_quote("AAPL")


def test_fmp_quote_invalid_shape():
    response = Mock()
    response.json.return_value = {"error": "bad"}

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ):
        with pytest.raises(DataValidationError):
            FMPClient().get_quote("AAPL")


def test_fmp_quote_empty_response():
    response = Mock()
    response.json.return_value = []

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ):
        with pytest.raises(DataValidationError):
            FMPClient().get_quote("AAPL")


def test_fmp_quote_invalid_item():
    response = Mock()
    response.json.return_value = ["invalid"]

    with patch(
        "quantcore.ingestion.providers.fmp.requests.get",
        return_value=response,
    ):
        with pytest.raises(DataValidationError):
            FMPClient().get_quote("AAPL")
