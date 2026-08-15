from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd

from quantcore.ingestion.providers.yahoo import YahooClient
from quantcore.schemas.company import CompanyData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData


def test_yahoo_get_company_info():

    fake_ticker = Mock()

    fake_ticker.info = {
        "longName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "website": "https://www.apple.com",
        "marketCap": 3000000000000,
    }

    with patch(
        "quantcore.ingestion.providers.yahoo.yf.Ticker",
        return_value=fake_ticker,
    ) as mock_ticker:

        result = YahooClient().get_company_info("AAPL")

    mock_ticker.assert_called_once_with("AAPL")

    assert isinstance(result, CompanyData)

    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
    assert result.sector == "Technology"
    assert result.industry == "Consumer Electronics"
    assert result.country == "United States"
    assert result.website == "https://www.apple.com"
    assert result.market_cap == 3000000000000


def test_yahoo_get_company_info_missing_fields():

    fake_ticker = Mock()

    fake_ticker.info = {
        "longName": "Apple Inc.",
    }

    with patch(
        "quantcore.ingestion.providers.yahoo.yf.Ticker",
        return_value=fake_ticker,
    ):
        result = YahooClient().get_company_info("AAPL")

    assert isinstance(result, CompanyData)

    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
    assert result.sector == ""
    assert result.industry == ""
    assert result.country == ""
    assert result.website == ""
    assert result.market_cap is None


def test_yahoo_get_price_history():

    fake_ticker = Mock()

    dates = pd.to_datetime(
        [
            "2025-01-02",
            "2025-01-03",
        ]
    )

    fake_history = pd.DataFrame(
        {
            "Open": [100.0, 105.0],
            "High": [110.0, 115.0],
            "Low": [95.0, 102.0],
            "Close": [108.0, 112.0],
            "Volume": [1000000, 1200000],
            "Dividends": [0.0, 0.25],
            "Stock Splits": [0.0, 0.0],
        },
        index=dates,
    )

    fake_ticker.history.return_value = fake_history

    with patch(
        "quantcore.ingestion.providers.yahoo.yf.Ticker",
        return_value=fake_ticker,
    ) as mock_ticker:

        result = YahooClient().get_price_history(
            "AAPL",
            period="5y",
        )

    mock_ticker.assert_called_once_with("AAPL")

    fake_ticker.history.assert_called_once_with(
        period="5y"
    )

    assert len(result) == 2

    assert all(
        isinstance(price, PriceData)
        for price in result
    )

    assert result[0].date == dates[0].to_pydatetime()
    assert result[0].open == 100.0
    assert result[0].high == 110.0
    assert result[0].low == 95.0
    assert result[0].close == 108.0
    assert result[0].volume == 1000000
    assert result[0].dividends == 0.0
    assert result[0].stock_splits == 0.0

    assert result[1].date == dates[1].to_pydatetime()
    assert result[1].open == 105.0
    assert result[1].close == 112.0
    assert result[1].volume == 1200000
    assert result[1].dividends == 0.25
    assert result[1].stock_splits == 0.0


def test_yahoo_get_price_history_empty():

    fake_ticker = Mock()

    fake_ticker.history.return_value = pd.DataFrame()

    with patch(
        "quantcore.ingestion.providers.yahoo.yf.Ticker",
        return_value=fake_ticker,
    ):
        result = YahooClient().get_price_history("AAPL")

    assert result == []


def test_yahoo_get_news():

    fake_ticker = Mock()

    published_timestamp = 1735819200000

    fake_ticker.news = [
        {
            "content": {
                "title": "Apple reports strong results",
                "summary": (
                    "Apple reported strong quarterly results."
                ),
                "pubDate": published_timestamp,
                "provider": {
                    "displayName": "Example News"
                },
                "canonicalUrl": {
                    "url": "https://example.com/apple"
                },
            }
        }
    ]

    with patch(
        "quantcore.ingestion.providers.yahoo.yf.Ticker",
        return_value=fake_ticker,
    ) as mock_ticker:

        result = YahooClient().get_news("AAPL")

    mock_ticker.assert_called_once_with("AAPL")

    assert len(result) == 1
    assert isinstance(result[0], NewsData)

    assert result[0].title == (
        "Apple reports strong results"
    )

    assert result[0].publisher == (
        "Example News"
    )

    assert result[0].summary == (
        "Apple reported strong quarterly results."
    )

    assert result[0].url == (
        "https://example.com/apple"
    )

    assert result[0].published_at == (
        datetime.fromtimestamp(
            published_timestamp / 1000
        )
    )