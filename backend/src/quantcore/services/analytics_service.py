from sqlalchemy.orm import Session

from quantcore.analytics import (
    MovingAverage,
    ExponentialMovingAverage,
    MACD,
)
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.price_repository import PriceRepository


class AnalyticsService:

    def __init__(self, db: Session):
        self.company_repo = CompanyRepository(db)
        self.price_repo = PriceRepository(db)

    def sma(
        self,
        symbol: str,
        period: int = 20,
    ):

        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(
                f"{symbol} not found."
            )

        prices = self.price_repo.get_for_company(company.id)

        close_prices = [
            p.close for p in prices
        ]

        sma_values = MovingAverage.sma(
            close_prices,
            period,
        )

        result = []

        for price, sma in zip(prices, sma_values):

            result.append(
                {
                    "date": price.date,
                    "close": price.close,
                    "sma": sma,
                }
            )

        return result

    def ema(
        self,
        symbol: str,
        period: int = 20,
    ):

        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(
                f"{symbol} not found."
            )

        prices = self.price_repo.get_for_company(company.id)

        close_prices = [
            p.close for p in prices
        ]

        ema_values = ExponentialMovingAverage.ema(
            close_prices,
            period,
        )

        result = []

        for price, ema in zip(prices, ema_values):

            result.append(
                {
                    "date": price.date,
                    "close": price.close,
                    "ema": ema,
                }
            )

        return result

    def macd(
        self,
        symbol: str,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):

        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(
                f"{symbol} not found."
            )

        prices = self.price_repo.get_for_company(company.id)

        close_prices = [
            p.close for p in prices
        ]

        macd_values = MACD.macd(
            close_prices,
            fast_period,
            slow_period,
            signal_period,
        )

        result = []

        for price, values in zip(prices, macd_values):

            result.append(
                {
                    "date": price.date,
                    "close": price.close,
                    "macd": values["macd"],
                    "signal": values["signal"],
                    "histogram": values["histogram"],
                }
            )

        return result