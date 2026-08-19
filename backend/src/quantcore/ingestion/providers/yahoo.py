from datetime import datetime

import yfinance as yf

from quantcore.core.exceptions import (
    DataValidationError,
    ExternalDataError,
    InvalidInputError,
)
from quantcore.schemas.company import CompanyData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData

from .base import MarketDataProvider


class YahooClient(MarketDataProvider):
    """Yahoo Finance market-data provider."""

    def get_company_info(self, symbol: str) -> CompanyData:
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
        except Exception as exc:
            raise ExternalDataError(
                "Failed to retrieve company data from Yahoo Finance."
            ) from exc

        if not isinstance(info, dict):
            raise DataValidationError(
                "Yahoo company response must be an object."
            )

        try:
            return CompanyData(
                symbol=symbol,
                name=info.get("longName", ""),
                sector=info.get("sector", ""),
                industry=info.get("industry", ""),
                country=info.get("country", ""),
                website=info.get("website", ""),
                market_cap=info.get("marketCap"),
            )
        except (TypeError, ValueError) as exc:
            raise DataValidationError(
                "Invalid Yahoo company data."
            ) from exc

    def get_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> list[PriceData]:
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        if not period:
            raise InvalidInputError("Period must not be empty.")

        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period=period)
        except Exception as exc:
            raise ExternalDataError(
                "Failed to retrieve price history from Yahoo Finance."
            ) from exc

        if history.empty:
            return []

        required_columns = {
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        }
        missing_columns = required_columns - set(history.columns)

        if missing_columns:
            raise DataValidationError(
                "Yahoo price response is missing required columns: "
                f"{sorted(missing_columns)}"
            )

        prices: list[PriceData] = []

        try:
            for timestamp, row in history.iterrows():
                prices.append(
                    PriceData(
                        date=timestamp.to_pydatetime(),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]),
                        dividends=float(row.get("Dividends", 0.0)),
                        stock_splits=float(
                            row.get("Stock Splits", 0.0)
                        ),
                    )
                )
        except (TypeError, ValueError, OverflowError) as exc:
            raise DataValidationError(
                "Invalid Yahoo price data."
            ) from exc

        return prices

    def get_news(self, symbol: str) -> list[NewsData]:
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        try:
            ticker = yf.Ticker(symbol)
            raw_articles = ticker.news
        except Exception as exc:
            raise ExternalDataError(
                "Failed to retrieve news from Yahoo Finance."
            ) from exc

        if not isinstance(raw_articles, list):
            raise DataValidationError(
                "Yahoo news response must be a list."
            )

        articles: list[NewsData] = []

        for item in raw_articles:
            if not isinstance(item, dict):
                raise DataValidationError(
                    "Yahoo news item must be an object."
                )

            content = item.get("content", {})
            if not isinstance(content, dict):
                raise DataValidationError(
                    "Yahoo news content must be an object."
                )

            provider = content.get("provider", {})
            if not isinstance(provider, dict):
                provider = {}

            canonical = content.get("canonicalUrl", {})
            if not isinstance(canonical, dict):
                canonical = {}

            published_at = None
            pub_date = content.get("pubDate")

            if pub_date is not None:
                try:
                    published_at = datetime.fromtimestamp(
                        float(pub_date) / 1000
                    )
                except (TypeError, ValueError, OverflowError):
                    published_at = None

            try:
                articles.append(
                    NewsData(
                        title=content.get("title", ""),
                        publisher=provider.get("displayName", ""),
                        summary=content.get("summary", ""),
                        url=canonical.get("url", ""),
                        published_at=published_at,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise DataValidationError(
                    "Invalid Yahoo news item."
                ) from exc

        return articles
