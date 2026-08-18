from datetime import datetime

import yfinance as yf

from quantcore.core.exceptions import InvalidInputError
from quantcore.schemas.company import CompanyData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData

from .base import MarketDataProvider


class YahooClient(MarketDataProvider):
    """
    Yahoo Finance data ingestion client.

    The provider is responsible for communicating with Yahoo Finance
    and converting Yahoo responses into QuantCore domain schemas.

    Transport/provider exceptions intentionally propagate to the
    service layer. They are not translated into API errors here.
    """

    def get_company_info(
        self,
        symbol: str,
    ) -> CompanyData:
        """
        Retrieve company information from Yahoo Finance.
        """

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        ticker = yf.Ticker(symbol)

        info = ticker.info

        if not isinstance(info, dict):
            raise ValueError(
                "Yahoo company response must be an object."
            )

        return CompanyData(
            symbol=symbol,
            name=info.get("longName", ""),
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            country=info.get("country", ""),
            website=info.get("website", ""),
            market_cap=info.get("marketCap"),
        )

    def get_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> list[PriceData]:
        """
        Retrieve historical price data from Yahoo Finance.
        """

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        if not period:
            raise InvalidInputError(
                "Period must not be empty."
            )

        ticker = yf.Ticker(symbol)

        history = ticker.history(
            period=period
        )

        if history.empty:
            return []

        required_columns = {
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        }

        missing_columns = (
            required_columns
            - set(history.columns)
        )

        if missing_columns:
            raise ValueError(
                "Yahoo price response is missing "
                f"required columns: "
                f"{sorted(missing_columns)}"
            )

        prices: list[PriceData] = []

        for date, row in history.iterrows():

            prices.append(
                PriceData(
                    date=date.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                    dividends=float(
                        row.get("Dividends", 0.0)
                    ),
                    stock_splits=float(
                        row.get("Stock Splits", 0.0)
                    ),
                )
            )

        return prices

    def get_news(
        self,
        symbol: str,
    ) -> list[NewsData]:
        """
        Retrieve recent news articles from Yahoo Finance.
        """

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        ticker = yf.Ticker(symbol)

        raw_articles = ticker.news

        if not isinstance(raw_articles, list):
            raise ValueError(
                "Yahoo news response must be a list."
            )

        articles: list[NewsData] = []

        for item in raw_articles:

            if not isinstance(item, dict):
                raise ValueError(
                    "Yahoo news item must be an object."
                )

            content = item.get("content", {})

            if not isinstance(content, dict):
                raise ValueError(
                    "Yahoo news content must be an object."
                )

            provider = content.get(
                "provider",
                {},
            )

            if not isinstance(provider, dict):
                provider = {}

            canonical = content.get(
                "canonicalUrl",
                {},
            )

            if not isinstance(canonical, dict):
                canonical = {}

            published_at = None

            pub_date = content.get("pubDate")

            if pub_date is not None:
                try:
                    published_at = datetime.fromtimestamp(
                        float(pub_date) / 1000
                    )
                except (
                    TypeError,
                    ValueError,
                    OverflowError,
                ):
                    published_at = None

            articles.append(
                NewsData(
                    title=content.get(
                        "title",
                        "",
                    ),
                    publisher=provider.get(
                        "displayName",
                        "",
                    ),
                    summary=content.get(
                        "summary",
                        "",
                    ),
                    url=canonical.get(
                        "url",
                        "",
                    ),
                    published_at=published_at,
                )
            )

        return articles