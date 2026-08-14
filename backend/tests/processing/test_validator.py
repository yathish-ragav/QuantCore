from datetime import datetime
from types import SimpleNamespace

from quantcore.processing.validator import DataValidator


def make_company(**overrides):
    data = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "website": "https://apple.com",
        "market_cap": 3_000_000_000_000,
    }

    data.update(overrides)

    return SimpleNamespace(**data)


def make_price(**overrides):
    data = {
        "date": datetime(2026, 1, 2),
        "open": 250.0,
        "high": 255.0,
        "low": 248.0,
        "close": 253.0,
        "volume": 1_000_000,
        "dividends": 0.0,
        "stock_splits": 0.0,
    }

    data.update(overrides)

    return SimpleNamespace(**data)


def make_news(**overrides):
    data = {
        "title": "Apple reports strong quarterly results",
        "publisher": "Reuters",
        "summary": "Apple reported strong quarterly results.",
        "url": "https://example.com/article",
        "published_at": datetime(2026, 1, 2),
    }

    data.update(overrides)

    return SimpleNamespace(**data)


def test_validate_company_accepts_valid_company():
    company = make_company()

    assert DataValidator.validate_company(company) is True


def test_validate_company_rejects_missing_symbol():
    company = make_company(symbol="")

    assert DataValidator.validate_company(company) is False


def test_validate_company_rejects_negative_market_cap():
    company = make_company(market_cap=-100)

    assert DataValidator.validate_company(company) is False


def test_validate_company_accepts_missing_market_cap():
    company = make_company(market_cap=None)

    assert DataValidator.validate_company(company) is True


def test_validate_price_accepts_valid_price():
    price = make_price()

    assert DataValidator.validate_price(price) is True


def test_validate_price_rejects_invalid_ohlc():
    price = make_price(
        high=240.0,
        low=248.0,
    )

    assert DataValidator.validate_price(price) is False


def test_validate_price_rejects_open_above_high():
    price = make_price(
        open=260.0,
        high=255.0,
    )

    assert DataValidator.validate_price(price) is False


def test_validate_price_rejects_close_below_low():
    price = make_price(
        close=240.0,
        low=248.0,
    )

    assert DataValidator.validate_price(price) is False


def test_validate_price_rejects_negative_volume():
    price = make_price(volume=-1)

    assert DataValidator.validate_price(price) is False


def test_validate_price_rejects_invalid_date():
    price = make_price(
        date="2026-01-02",
    )

    assert DataValidator.validate_price(price) is False


def test_validate_news_accepts_valid_article():
    article = make_news()

    assert DataValidator.validate_news(article) is True


def test_validate_news_rejects_empty_title():
    article = make_news(title="")

    assert DataValidator.validate_news(article) is False


def test_validate_news_rejects_missing_url():
    article = make_news(url="")

    assert DataValidator.validate_news(article) is False


def test_validate_news_accepts_missing_published_at():
    article = make_news(published_at=None)

    assert DataValidator.validate_news(article) is True


def test_validate_prices_accepts_valid_list():
    prices = [
        make_price(),
        make_price(
            date=datetime(2026, 1, 3),
        ),
    ]

    assert DataValidator.validate_prices(prices) is True


def test_validate_prices_rejects_invalid_price():
    prices = [
        make_price(),
        make_price(volume=-100),
    ]

    assert DataValidator.validate_prices(prices) is False


def test_validate_news_articles_accepts_valid_list():
    articles = [
        make_news(),
        make_news(
            url="https://example.com/second",
        ),
    ]

    assert (
        DataValidator.validate_news_articles(articles)
        is True
    )


def test_validate_news_articles_rejects_invalid_article():
    articles = [
        make_news(),
        make_news(title=""),
    ]

    assert (
        DataValidator.validate_news_articles(articles)
        is False
    )


def test_validate_companies_accepts_valid_list():
    companies = [
        make_company(),
        make_company(symbol="MSFT"),
    ]

    assert (
        DataValidator.validate_companies(companies)
        is True
    )


def test_validate_companies_rejects_invalid_company():
    companies = [
        make_company(),
        make_company(symbol=""),
    ]

    assert (
        DataValidator.validate_companies(companies)
        is False
    )


def test_validate_price_rejects_nan():
    price = make_price(open=float("nan"))

    assert DataValidator.validate_price(price) is False


def test_validate_price_rejects_infinite_value():
    price = make_price(close=float("inf"))

    assert DataValidator.validate_price(price) is False