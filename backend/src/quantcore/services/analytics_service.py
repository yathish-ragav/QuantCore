from sqlalchemy.orm import Session

from quantcore.analytics import (
    MovingAverage,
    ExponentialMovingAverage,
    MACD,
    RelativeStrengthIndex,
    BollingerBands,
    AverageTrueRange,
    AverageDirectionalIndex,
    Supertrend,
    StochasticOscillator,
    ParabolicSAR,
    VolumeWeightedAveragePrice,
)
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.price_repository import PriceRepository


class AnalyticsService:

    def __init__(self, db: Session):
        self.company_repo = CompanyRepository(db)
        self.price_repo = PriceRepository(db)

    def _get_prices(self, symbol: str):

        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(
                f"{symbol} not found."
            )

        return self.price_repo.get_for_company(company.id)

    def sma(
        self,
        symbol: str,
        period: int = 20,
    ):

        prices = self._get_prices(symbol)

        close_prices = [p.close for p in prices]

        sma_values = MovingAverage.sma(
            close_prices,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "sma": sma,
            }
            for price, sma in zip(prices, sma_values)
        ]

    def ema(
        self,
        symbol: str,
        period: int = 20,
    ):

        prices = self._get_prices(symbol)

        close_prices = [p.close for p in prices]

        ema_values = ExponentialMovingAverage.ema(
            close_prices,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "ema": ema,
            }
            for price, ema in zip(prices, ema_values)
        ]

    def macd(
        self,
        symbol: str,
    ):

        prices = self._get_prices(symbol)

        close_prices = [p.close for p in prices]

        macd_values = MACD.macd(
            close_prices,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "macd": value["macd"],
                "signal": value["signal"],
                "histogram": value["histogram"],
            }
            for price, value in zip(prices, macd_values)
        ]

    def rsi(
        self,
        symbol: str,
        period: int = 14,
    ):

        prices = self._get_prices(symbol)

        close_prices = [p.close for p in prices]

        rsi_values = RelativeStrengthIndex.rsi(
            close_prices,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "rsi": rsi,
            }
            for price, rsi in zip(prices, rsi_values)
        ]

    def bollinger(
        self,
        symbol: str,
        period: int = 20,
    ):

        prices = self._get_prices(symbol)

        close_prices = [p.close for p in prices]

        band_values = BollingerBands.calculate(
            close_prices,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "middle": band["middle"],
                "upper": band["upper"],
                "lower": band["lower"],
            }
            for price, band in zip(prices, band_values)
        ]

    def atr(
        self,
        symbol: str,
        period: int = 14,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        atr_values = AverageTrueRange.atr(
            highs,
            lows,
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "atr": atr,
            }
            for price, atr in zip(prices, atr_values)
        ]

    def adx(
        self,
        symbol: str,
        period: int = 14,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        adx_values = AverageDirectionalIndex.adx(
            highs,
            lows,
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "adx": adx,
            }
            for price, adx in zip(prices, adx_values)
        ]

    def supertrend(
        self,
        symbol: str,
        period: int = 10,
        multiplier: float = 3.0,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        values = SuperTrend.calculate(
            highs,
            lows,
            closes,
            period,
            multiplier,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "supertrend": value,
            }
            for price, value in zip(prices, values)
        ]

    def stochastic(
        self,
        symbol: str,
        period: int = 14,
        signal_period: int = 3,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        values = StochasticOscillator.calculate(
            highs,
            lows,
            closes,
            period,
            signal_period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "k": value["k"],
                "d": value["d"],
            }
            for price, value in zip(prices, values)
        ]

    def parabolic_sar(
        self,
        symbol: str,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]

        values = ParabolicSAR.calculate(
            highs,
            lows,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "psar": value,
            }
            for price, value in zip(prices, values)
        ]

    def vwap(
        self,
        symbol: str,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = VolumeWeightedAveragePrice.calculate(
            highs,
            lows,
            closes,
            volumes,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "volume": price.volume,
                "vwap": value,
            }
            for price, value in zip(prices, values)
        ]