from datetime import datetime

import pytest

from quantcore.processing.transformer import DataTransformer
from quantcore.schemas.company import CompanyData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData


def company_dict():
    return {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "website": "https://apple.com",
        "market_cap": 3_000_000_000_000,
    }


def price_dict():
    return {
        "date": datetime(2026, 1, 2),
        "open": 250.0,
        "high": 255.0,
        "low": 248.0,
        "close": 253.0,
        "volume": 1_000_000,
        "dividends": 0.0,
        "stock_splits": 0.0,
    }


def news_dict():
    return {
        "title": "Apple reports strong results",
        "publisher": "Reuters",
        "summary": "Apple reported strong quarterly results.",
        "url": "https://example.com/article",
        "published_at": datetime(2026, 1, 2),
    }


def test_company_returns_existing_schema():
    data = CompanyData(**company_dict())

    result = DataTransformer.company(data)

    assert result is data
    assert isinstance(result, CompanyData)


def test_company_transforms_dictionary():
    result = DataTransformer.company(company_dict())

    assert isinstance(result, CompanyData)
    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."


def test_company_rejects_invalid_type():
    with pytest.raises(TypeError):
        DataTransformer.company("AAPL")


def test_price_returns_existing_schema():
    data = PriceData(**price_dict())

    result = DataTransformer.price(data)

    assert result is data
    assert isinstance(result, PriceData)


def test_price_transforms_dictionary():
    result = DataTransformer.price(price_dict())

    assert isinstance(result, PriceData)
    assert result.close == 253.0
    assert result.volume == 1_000_000


def test_price_rejects_invalid_type():
    with pytest.raises(TypeError):
        DataTransformer.price("invalid")


def test_news_returns_existing_schema():
    data = NewsData(**news_dict())

    result = DataTransformer.news(data)

    assert result is data
    assert isinstance(result, NewsData)


def test_news_transforms_dictionary():
    result = DataTransformer.news(news_dict())

    assert isinstance(result, NewsData)
    assert result.title == "Apple reports strong results"
    assert result.publisher == "Reuters"


def test_news_rejects_invalid_type():
    with pytest.raises(TypeError):
        DataTransformer.news("invalid")


def test_companies_transforms_list():
    result = DataTransformer.companies(
        [
            company_dict(),
            company_dict(),
        ]
    )

    assert len(result) == 2
    assert all(
        isinstance(item, CompanyData)
        for item in result
    )


def test_companies_rejects_non_list():
    with pytest.raises(TypeError):
        DataTransformer.companies(company_dict())


def test_prices_transforms_list():
    result = DataTransformer.prices(
        [
            price_dict(),
            price_dict(),
        ]
    )

    assert len(result) == 2
    assert all(
        isinstance(item, PriceData)
        for item in result
    )


def test_prices_rejects_non_list():
    with pytest.raises(TypeError):
        DataTransformer.prices(price_dict())


def test_news_articles_transforms_list():
    result = DataTransformer.news_articles(
        [
            news_dict(),
            news_dict(),
        ]
    )

    assert len(result) == 2
    assert all(
        isinstance(item, NewsData)
        for item in result
    )


def test_news_articles_rejects_non_list():
    with pytest.raises(TypeError):
        DataTransformer.news_articles(news_dict())