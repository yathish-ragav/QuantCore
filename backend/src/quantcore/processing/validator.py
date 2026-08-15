from datetime import date, datetime
from math import isfinite


class DataValidator:

    @staticmethod
    def validate_company(data) -> bool:
        if not data:
            return False

        required_fields = [
            "symbol",
            "name",
            "sector",
            "industry",
            "country",
            "website",
        ]

        for field in required_fields:
            value = getattr(data, field, None)

            if not isinstance(value, str):
                return False

            if not value.strip():
                return False

        market_cap = getattr(data, "market_cap", None)

        if market_cap is not None:
            if not isinstance(market_cap, int):
                return False

            if market_cap < 0:
                return False

        return True

    @staticmethod
    def validate_price(data) -> bool:
        if not data:
            return False

        date = getattr(data, "date", None)

        if not isinstance(date, datetime):
            return False

        numeric_fields = [
            "open",
            "high",
            "low",
            "close",
        ]

        for field in numeric_fields:
            value = getattr(data, field, None)

            if not isinstance(value, (int, float)):
                return False

            if not isfinite(value):
                return False

            if value < 0:
                return False

        volume = getattr(data, "volume", None)

        if not isinstance(volume, int):
            return False

        if volume < 0:
            return False

        dividends = getattr(data, "dividends", None)

        if not isinstance(dividends, (int, float)):
            return False

        if not isfinite(dividends):
            return False

        stock_splits = getattr(
            data,
            "stock_splits",
            0.0,
        )

        if not isinstance(
            stock_splits,
            (int, float),
        ):
            return False

        if not isfinite(stock_splits):
            return False

        # OHLC consistency checks
        open_price = data.open
        high_price = data.high
        low_price = data.low
        close_price = data.close

        if high_price < low_price:
            return False

        if high_price < open_price:
            return False

        if high_price < close_price:
            return False

        if low_price > open_price:
            return False

        if low_price > close_price:
            return False

        return True

    @staticmethod
    def validate_news(data) -> bool:
        if not data:
            return False

        required_fields = [
            "title",
            "publisher",
            "summary",
            "url",
        ]

        for field in required_fields:
            value = getattr(data, field, None)

            if not isinstance(value, str):
                return False

            if not value.strip():
                return False

        published_at = getattr(
            data,
            "published_at",
            None,
        )

        if published_at is not None:
            if not isinstance(
                published_at,
                datetime,
            ):
                return False

        return True

    @staticmethod
    def validate_income_statement(data) -> bool:
        if not data:
            return False

        fiscal_date = getattr(
            data,
            "fiscal_date",
            None,
        )

        if not isinstance(fiscal_date, date):
            return False

        numeric_fields = [
            "total_revenue",
            "gross_profit",
            "operating_income",
            "net_income",
            "eps",
        ]

        for field in numeric_fields:
            value = getattr(
                data,
                field,
                None,
            )

            if value is None:
                continue

            if not isinstance(
                value,
                (int, float),
            ):
                return False

            if not isfinite(value):
                return False

        shares_outstanding = getattr(
            data,
            "shares_outstanding",
            None,
        )

        if shares_outstanding is not None:
            if not isinstance(
                shares_outstanding,
                int,
            ):
                return False

            if shares_outstanding < 0:
                return False

        return True

    @staticmethod
    def validate_prices(data) -> bool:
        if data is None:
            return False

        if not isinstance(data, list):
            return False

        return all(
            DataValidator.validate_price(price)
            for price in data
        )

    @staticmethod
    def validate_news_articles(data) -> bool:
        if data is None:
            return False

        if not isinstance(data, list):
            return False

        return all(
            DataValidator.validate_news(article)
            for article in data
        )

    @staticmethod
    def validate_income_statements(data) -> bool:
        if data is None:
            return False

        if not isinstance(data, list):
            return False

        return all(
            DataValidator.validate_income_statement(
                statement
            )
            for statement in data
        )

    @staticmethod
    def validate_companies(data) -> bool:
        if data is None:
            return False

        if not isinstance(data, list):
            return False

        return all(
            DataValidator.validate_company(company)
            for company in data
        )