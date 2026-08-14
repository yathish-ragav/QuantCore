from __future__ import annotations

import re

from quantcore.schemas.company import CompanyData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData


class DataCleaner:
    """
    Normalizes provider data before validation and transformation.

    The cleaner does not decide whether data is valid.
    It only removes formatting inconsistencies.
    """

    @staticmethod
    def clean_symbol(symbol: str) -> str:
        if not isinstance(symbol, str):
            raise TypeError("Symbol must be a string.")

        return symbol.strip().upper()

    @staticmethod
    def clean_text(value: str | None) -> str:
        if value is None:
            return ""

        if not isinstance(value, str):
            raise TypeError("Text value must be a string or None.")

        return re.sub(
            r"\s+",
            " ",
            value.strip(),
        )

    @classmethod
    def clean_company(
        cls,
        data: CompanyData,
    ) -> CompanyData:

        return CompanyData(
            symbol=cls.clean_symbol(data.symbol),
            name=cls.clean_text(data.name),
            sector=cls.clean_text(data.sector),
            industry=cls.clean_text(data.industry),
            country=cls.clean_text(data.country),
            website=cls.clean_text(data.website),
            market_cap=data.market_cap,
        )

    @classmethod
    def clean_news(
        cls,
        data: NewsData,
    ) -> NewsData:

        return NewsData(
            title=cls.clean_text(data.title),
            publisher=cls.clean_text(data.publisher),
            summary=cls.clean_text(data.summary),
            url=cls.clean_text(data.url),
            published_at=data.published_at,
        )

    @staticmethod
    def clean_price(
        data: PriceData,
    ) -> PriceData:

        return PriceData(
            date=data.date,
            open=float(data.open),
            high=float(data.high),
            low=float(data.low),
            close=float(data.close),
            volume=int(data.volume),
            dividends=float(data.dividends),
            stock_splits=float(data.stock_splits),
        )