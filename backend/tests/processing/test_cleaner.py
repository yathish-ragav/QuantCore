from datetime import datetime

from quantcore.processing.cleaner import DataCleaner
from quantcore.schemas.company import CompanyData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData


def test_clean_symbol_normalizes_symbol():

    result = DataCleaner.clean_symbol(
        "  aapl  "
    )

    assert result == "AAPL"


def test_clean_text_normalizes_whitespace():

    result = DataCleaner.clean_text(
        "  Apple     Inc.   "
    )

    assert result == "Apple Inc."


def test_clean_text_handles_none():

    result = DataCleaner.clean_text(None)

    assert result == ""


def test_clean_company_normalizes_fields():

    company = CompanyData(
        symbol="  aapl ",
        name="  Apple     Inc. ",
        sector=" Technology ",
        industry="  Consumer   Electronics ",
        country=" USA ",
        website=" https://apple.com ",
        market_cap=3_000_000_000_000,
    )

    result = DataCleaner.clean_company(
        company
    )

    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
    assert result.sector == "Technology"
    assert result.industry == "Consumer Electronics"
    assert result.country == "USA"
    assert result.website == "https://apple.com"
    assert result.market_cap == 3_000_000_000_000


def test_clean_news_normalizes_text():

    news = NewsData(
        title="  Apple     reports earnings  ",
        publisher="  Reuters  ",
        summary=" Apple reported    strong results. ",
        url=" https://example.com/article ",
        published_at=datetime(
            2026,
            1,
            2,
        ),
    )

    result = DataCleaner.clean_news(
        news
    )

    assert result.title == "Apple reports earnings"
    assert result.publisher == "Reuters"
    assert result.summary == (
        "Apple reported strong results."
    )
    assert result.url == (
        "https://example.com/article"
    )


def test_clean_price_normalizes_numeric_types():

    price = PriceData(
        date=datetime(
            2026,
            1,
            2,
        ),
        open=250,
        high=255,
        low=248,
        close=253,
        volume=1_000_000,
        dividends=0,
        stock_splits=0,
    )

    result = DataCleaner.clean_price(
        price
    )

    assert result.open == 250.0
    assert result.high == 255.0
    assert result.low == 248.0
    assert result.close == 253.0
    assert result.volume == 1_000_000
    assert result.dividends == 0.0
    assert result.stock_splits == 0.0