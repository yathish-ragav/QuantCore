from unittest.mock import Mock, patch

import pytest
import requests

from quantcore.core.enums import CorporateActionType
from quantcore.core.exceptions import ExternalDataError, RateLimitError
from quantcore.ingestion.providers.massive import MassiveClient


@pytest.fixture
def client():
    with patch(
        "quantcore.ingestion.providers.massive.settings.MASSIVE_API_KEY",
        "test-key",
    ):
        return MassiveClient()


def test_massive_requires_api_key():
    with patch(
        "quantcore.ingestion.providers.massive.settings.MASSIVE_API_KEY",
        "",
    ):
        with pytest.raises(Exception, match="MASSIVE_API_KEY"):
            MassiveClient()


def test_massive_price_history_joins_adjusted_close(client):
    responses = [
        {
            "status": "OK",
            "results": [
                {
                    "t": 1735833600000,
                    "o": 100,
                    "h": 110,
                    "l": 95,
                    "c": 105,
                    "v": 1000,
                }
            ],
        },
        {
            "status": "OK",
            "results": [
                {
                    "t": 1735833600000,
                    "o": 50,
                    "h": 55,
                    "l": 47,
                    "c": 52.5,
                    "v": 1000,
                }
            ],
        },
    ]

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        side_effect=[
            Mock(status_code=200, json=lambda: responses[0]),
            Mock(status_code=200, json=lambda: responses[1]),
        ],
    ):
        result = client.get_price_history("AAPL", period="1d")

    assert len(result) == 1
    assert result[0].close == 105
    assert result[0].adjusted_close == 52.5
    assert result[0].volume == 1000


def test_massive_price_history_accepts_delayed_status(client):
    response = {
        "status": "DELAYED",
        "results": [
            {
                "t": 1735833600000,
                "o": 100,
                "h": 110,
                "l": 95,
                "c": 105,
                "v": 1000,
            }
        ],
    }
    adjusted_response = {
        "status": "DELAYED",
        "results": [
            {
                "t": 1735833600000,
                "o": 50,
                "h": 55,
                "l": 47,
                "c": 52.5,
                "v": 1000,
            }
        ],
    }

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        side_effect=[
            Mock(status_code=200, json=lambda: response),
            Mock(status_code=200, json=lambda: adjusted_response),
        ],
    ):
        result = client.get_price_history("AAPL", period="1d")

    assert len(result) == 1
    assert result[0].close == 105
    assert result[0].adjusted_close == 52.5


def test_massive_reference_endpoint_does_not_accept_delayed_status(client):
    response = {"status": "DELAYED", "results": {"ticker": "AAPL", "name": "Apple Inc."}}

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        return_value=Mock(status_code=200, json=lambda: response),
    ):
        with pytest.raises(ExternalDataError, match="Massive returned status 'DELAYED'"):
            client.get_company_info("AAPL")


def test_massive_rejects_unaccepted_status(client):
    response = {"status": "ERROR", "error": "bad request"}

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        return_value=Mock(status_code=200, json=lambda: response),
    ):
        with pytest.raises(ExternalDataError, match="Massive returned status 'ERROR'"):
            client.get_price_history("AAPL", period="1d")


def test_massive_corporate_actions(client):
    dividend_response = {
        "status": "OK",
        "results": [
            {
                "id": "div-1",
                "ex_dividend_date": "2025-08-11",
                "cash_amount": 0.26,
            }
        ],
    }
    split_response = {
        "status": "OK",
        "results": [
            {
                "id": "split-1",
                "execution_date": "2024-08-12",
                "split_from": 1,
                "split_to": 4,
            }
        ],
    }

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        side_effect=[
            Mock(status_code=200, json=lambda: dividend_response),
            Mock(status_code=200, json=lambda: split_response),
        ],
    ):
        result = client.get_corporate_actions("AAPL")

    assert len(result) == 2
    assert result[0].action_type is CorporateActionType.STOCK_SPLIT
    assert result[0].split_ratio == 4
    assert result[0].source_reference == "MASSIVE:STOCK_SPLIT:split-1"
    assert result[1].action_type is CorporateActionType.DIVIDEND
    assert result[1].amount == 0.26
    assert result[1].source_reference == "MASSIVE:DIVIDEND:div-1"


def test_massive_news(client):
    response = {
        "status": "OK",
        "results": [
            {
                "id": "article-1",
                "title": "Apple update",
                "description": "Summary",
                "article_url": "https://example.com/article",
                "published_utc": "2026-09-15T12:00:00Z",
                "publisher": {"name": "Example"},
            }
        ],
    }

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        return_value=Mock(status_code=200, json=lambda: response),
    ):
        result = client.get_news("AAPL")

    assert len(result) == 1
    assert result[0].title == "Apple update"
    assert result[0].publisher == "Example"


def test_massive_quote_rejects_wrong_ticker(client):
    response = {
        "status": "OK",
        "results": [
            {
                "ticker": "MSFT",
                "name": "Microsoft Corporation",
                "session": {"price": 500.0, "previous_close": 495.0},
            }
        ],
    }

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        return_value=Mock(status_code=200, json=lambda: response),
    ):
        with pytest.raises(Exception, match="returned ticker"):
            client.get_quote("AAPL")


def test_massive_quote(client):
    response = {
        "status": "OK",
        "results": [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "session": {
                    "price": 250.0,
                    "previous_close": 245.0,
                    "open": 246.0,
                    "low": 244.0,
                    "high": 251.0,
                    "volume": 1000000,
                    "last_updated": 1760000000000000000,
                },
            }
        ],
    }

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        return_value=Mock(status_code=200, json=lambda: response),
    ):
        result = client.get_quote("AAPL")

    assert result.symbol == "AAPL"
    assert result.price == 250.0
    assert result.change == 5.0
    assert result.change_percent == pytest.approx(100 * 5 / 245)


def test_massive_http_error_boundary(client):
    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        side_effect=requests.RequestException("network"),
    ):
        with pytest.raises(Exception, match="Massive market-data request failed"):
            client.get_company_info("AAPL")


def test_massive_http_429_raises_rate_limit_error_with_retry_after(client):
    response = Mock(
        status_code=429,
        headers={"Retry-After": "17"},
    )

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        return_value=response,
    ):
        with pytest.raises(RateLimitError) as exc_info:
            client.get_company_info("AAPL")

    assert exc_info.value.retry_after_seconds == 17.0


def test_massive_http_429_defaults_to_safe_retry_delay(client):
    response = Mock(status_code=429, headers={})

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        return_value=response,
    ):
        with pytest.raises(RateLimitError) as exc_info:
            client.get_company_info("AAPL")

    assert exc_info.value.retry_after_seconds == 60.0


def test_massive_company_info_maps_documented_reference_fields_without_fabricating_sector(client):
    response = {
        "status": "OK",
        "results": {
            "active": True,
            "address": {
                "address1": "One Apple Park Way",
                "city": "Cupertino",
                "state": "CA",
                "postal_code": "95014",
            },
            "cik": "0000320193",
            "homepage_url": "https://www.apple.com",
            "locale": "us",
            "market": "stocks",
            "market_cap": 2771126040150,
            "name": "Apple Inc.",
            "primary_exchange": "XNAS",
            "sic_code": "3571",
            "sic_description": "ELECTRONIC COMPUTERS",
            "ticker": "AAPL",
            "type": "CS",
        },
    }

    with patch(
        "quantcore.ingestion.providers.massive.requests.get",
        return_value=Mock(status_code=200, json=lambda: response),
    ):
        result = client.get_company_info("AAPL")

    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
    assert result.sector is None
    assert result.industry == "ELECTRONIC COMPUTERS"
    assert result.country == "United States"
    assert result.website == "https://www.apple.com"
    assert result.market_cap == 2771126040150
