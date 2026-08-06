from .base import MarketDataProvider
from datetime import datetime
import yfinance as yf

from quantcore.schemas.company import CompanyData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData


class YahooClient(MarketDataProvider):
    """
    Yahoo Finance data ingestion client.
    """

    def get_company_info(self, symbol: str) -> CompanyData:
        ticker = yf.Ticker(symbol)
        info = ticker.info

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

        ticker = yf.Ticker(symbol)
        history = ticker.history(period=period)

        prices = []

        for date, row in history.iterrows():
            prices.append(
                PriceData(
                    date=date.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                    dividends=float(row.get("Dividends", 0.0)),
                    stock_splits=float(row.get("Stock Splits", 0.0)),
                )
            )

        return prices

    def get_news(
        self,
        symbol: str,
    ) -> list[NewsData]:

        ticker = yf.Ticker(symbol)

        articles = []

        for item in ticker.news:

            content = item.get("content", {})

            provider = content.get("provider", {})
            canonical = content.get("canonicalUrl", {})

            published_at = None

            if content.get("pubDate"):
                try:
                    published_at = datetime.fromtimestamp(
                        content["pubDate"] / 1000
                    )
                except Exception:
                    pass

            articles.append(
                NewsData(
                    title=content.get("title", ""),
                    publisher=provider.get("displayName", ""),
                    summary=content.get("summary", ""),
                    url=canonical.get("url", ""),
                    published_at=published_at,
                )
            )

        return articles