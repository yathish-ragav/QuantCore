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
    OnBalanceVolume,
    MoneyFlowIndex,
    ChaikinMoneyFlow,
    IchimokuCloud,
    DonchianChannels,
    KeltnerChannels,
    CommodityChannelIndex,
    WilliamsR,
    RateOfChange,
    UltimateOscillator,
    TRIX,
    Aroon,
    AroonOscillator,
    DetrendedPriceOscillator,
    VortexIndicator,
    EaseOfMovement,
    AccumulationDistribution,
    ForceIndex,
    NegativeVolumeIndex,
    PositiveVolumeIndex,
    KlingerVolumeOscillator,
    ChaikinOscillator,
    ElderRayIndex,
    RelativeVigorIndex,
    CoppockCurve,
    KnowSureThing
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

        values = Supertrend.calculate(
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

    def obv(
        self,
        symbol: str,
    ):

        prices = self._get_prices(symbol)

        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = OnBalanceVolume.calculate(
            closes,
            volumes,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "volume": price.volume,
                "obv": value,
            }
            for price, value in zip(prices, values)
        ]

    def mfi(
        self,
        symbol: str,
        period: int = 14,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = MoneyFlowIndex.calculate(
            highs,
            lows,
            closes,
            volumes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "volume": price.volume,
                "mfi": value,
            }
            for price, value in zip(prices, values)
        ]

    def cmf(
        self,
        symbol: str,
        period: int = 20,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = ChaikinMoneyFlow.calculate(
            highs,
            lows,
            closes,
            volumes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "volume": price.volume,
                "cmf": value,
            }
            for price, value in zip(prices, values)
        ]

    def ichimoku(
        self,
        symbol: str,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]

        values = IchimokuCloud.calculate(
            highs,
            lows,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "tenkan": value["tenkan"],
                "kijun": value["kijun"],
                "span_a": value["span_a"],
                "span_b": value["span_b"],
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def donchian(
        self,
        symbol: str,
        period: int = 20,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]

        values = DonchianChannels.calculate(
            highs,
            lows,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "upper": value["upper"],
                "middle": value["middle"],
                "lower": value["lower"],
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def keltner(
        self,
        symbol: str,
        period: int = 20,
        multiplier: float = 2.0,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        channel_values = KeltnerChannels.calculate(
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
                "middle": channel["middle"],
                "upper": channel["upper"],
                "lower": channel["lower"],
            }
            for price, channel in zip(prices, channel_values)
        ]

    def cci(
        self,
        symbol: str,
        period: int = 20,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        cci_values = CommodityChannelIndex.calculate(
            highs,
            lows,
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "cci": cci,
            }
            for price, cci in zip(prices, cci_values)
        ]

    def williams_r(
        self,
        symbol: str,
        period: int = 14,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        wr_values = WilliamsR.calculate(
            highs,
            lows,
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "williams_r": wr,
            }
            for price, wr in zip(prices, wr_values)
        ]

    def roc(
        self,
        symbol: str,
        period: int = 12,
    ):

        prices = self._get_prices(symbol)

        closes = [p.close for p in prices]

        roc_values = RateOfChange.calculate(
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "roc": roc,
            }
            for price, roc in zip(prices, roc_values)
        ]

    def ultimate_oscillator(
        self,
        symbol: str,
        short_period: int = 7,
        medium_period: int = 14,
        long_period: int = 28,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        values = UltimateOscillator.calculate(
            highs,
            lows,
            closes,
            short_period,
            medium_period,
            long_period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "ultimate_oscillator": value,
            }
            for price, value in zip(prices, values)
        ]

    def trix(
        self,
        symbol: str,
        period: int = 15,
    ):

        prices = self._get_prices(symbol)

        closes = [p.close for p in prices]

        values = TRIX.calculate(
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "trix": value,
            }
            for price, value in zip(prices, values)
        ]

    def aroon(
            self,
            symbol: str,
            period: int = 25,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]

        values = Aroon.calculate(
            highs,
            lows,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "aroon_up": value["aroon_up"],
                "aroon_down": value["aroon_down"],
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def aroon_oscillator(
            self,
            symbol: str,
            period: int = 25,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]

        values = AroonOscillator.calculate(
            highs,
            lows,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "aroon_oscillator": value,
            }
            for price, value in zip(prices, values)
        ]

    def dpo(
            self,
            symbol: str,
            period: int = 20,
    ):

        prices = self._get_prices(symbol)

        closes = [p.close for p in prices]

        values = DetrendedPriceOscillator.calculate(
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "dpo": value,
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def vortex(
            self,
            symbol: str,
            period: int = 14,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        values = VortexIndicator.calculate(
            highs,
            lows,
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "vortex_plus": value["vortex_plus"],
                "vortex_minus": value["vortex_minus"],
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def emv(
            self,
            symbol: str,
            period: int = 14,
    ):
        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(f"{symbol} not found.")

        prices = self.price_repo.get_for_company(company.id)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        volumes = [p.volume for p in prices]

        emv_values = EaseOfMovement.emv(
            highs,
            lows,
            volumes,
            period,
        )

        result = []

        for price, emv in zip(prices, emv_values):
            result.append(
                {
                     "date": price.date,
                     "close": price.close,
                     "volume": price.volume,
                     "emv": emv,
                }
            )

        return result

    def accumulation_distribution(
        self,
        symbol: str,
    ):
        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(f"{symbol} not found.")

        prices = self.price_repo.get_for_company(company.id)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = AccumulationDistribution.ad(
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
                "accumulation_distribution": value,
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def force_index(
        self,
        symbol: str,
    ):
        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(f"{symbol} not found.")

        prices = self.price_repo.get_for_company(company.id)

        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = ForceIndex.force_index(
            closes,
            volumes,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "volume": price.volume,
                "force_index": value,
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def nvi(
        self,
        symbol: str,
    ):
        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(f"{symbol} not found.")

        prices = self.price_repo.get_for_company(company.id)

        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = NegativeVolumeIndex.calculate(
            closes,
            volumes,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "volume": price.volume,
                "nvi": value,
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def pvi(
        self,
        symbol: str,
    ):
        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(f"{symbol} not found.")

        prices = self.price_repo.get_for_company(company.id)

        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = PositiveVolumeIndex.calculate(
            closes,
            volumes,
        )

        return [
            {
            "date": price.date,
            "close": price.close,
            "volume": price.volume,
            "pvi": value,
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    
    def kvo(
        self,
        symbol: str,
        fast_period: int = 34,
        slow_period: int = 55,
        signal_period: int = 13,
    ):
        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(f"{symbol} not found.")

        prices = self.price_repo.get_for_company(company.id)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = KlingerVolumeOscillator.calculate(
            highs,
            lows,
            closes,
            volumes,
            fast_period,
            slow_period,
            signal_period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "volume": price.volume,
                "kvo": value["kvo"],
                "signal": value["signal"],
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def chaikin_oscillator(
        self,
        symbol: str,
        fast_period: int = 3,
        slow_period: int = 10,
    ):
        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(f"{symbol} not found.")

        prices = self.price_repo.get_for_company(company.id)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        values = ChaikinOscillator.calculate(
            highs,
            lows,
            closes,
            volumes,
            fast_period,
            slow_period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "volume": price.volume,
                "chaikin_oscillator": value,
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def elder_ray(
        self,
        symbol: str,
        period: int = 13,
    ):

        prices = self._get_prices(symbol)

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        values = ElderRayIndex.calculate(
            highs,
            lows,
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "bull_power": value["bull_power"],
                "bear_power": value["bear_power"],
            }
            for price, value in zip(prices, values)
        ]

    def rvi(
        self,
        symbol: str,
        period: int = 10,
    ):
        prices = self._get_prices(symbol)

        opens = [p.open for p in prices]
        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        closes = [p.close for p in prices]

        values = RelativeVigorIndex.calculate(
            opens,
            highs,
            lows,
            closes,
            period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "rvi": value,
            }
            for price, value in zip(prices, values)
        ]

    def coppock(
        self,
        symbol: str,
        roc_fast_period: int = 14,
        roc_slow_period: int = 11,
        wma_period: int = 10,
    ):
        prices = self._get_prices(symbol)

        closes = [p.close for p in prices]

        values = CoppockCurve.calculate(
            closes,
            roc_fast_period,
            roc_slow_period,
            wma_period,
        )

        return [
            {
                "date": price.date,
                "close": price.close,
                "coppock": value,
            }
            for price, value in zip(
                prices,
                values,
            )
        ]

    def kst(
          self,
          symbol: str,
          roc1_period: int = 10,
          roc2_period: int = 15,
          roc3_period: int = 20,
          roc4_period: int = 30,
          sma1_period: int = 10,
          sma2_period: int = 10,
          sma3_period: int = 10,
          sma4_period: int = 15,
    ):
          prices = self._get_prices(symbol)

          closes = [p.close for p in prices]

          values = KnowSureThing.calculate(
              closes,
              roc1_period,
              roc2_period,
              roc3_period,
              roc4_period,
              sma1_period,
              sma2_period,
              sma3_period,
              sma4_period,
          )

          return [
                {
                   "date": price.date,
                   "close": price.close,
                   "kst": value,
                }
                for price, value in zip(
                    prices,
                    values,
                )
            ]

   