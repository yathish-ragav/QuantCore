from typing import List

from .atr import AverageTrueRange


class SuperTrend:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 10,
        multiplier: float = 3.0,
    ):

        atr = AverageTrueRange.atr(
            highs,
            lows,
            closes,
            period,
        )

        result: List[float | None] = [None] * len(closes)

        upper_band: List[float | None] = []
        lower_band: List[float | None] = []

        for i in range(len(closes)):

            if atr[i] is None:

                upper_band.append(None)
                lower_band.append(None)

                continue

            hl2 = (highs[i] + lows[i]) / 2

            upper = hl2 + multiplier * atr[i]
            lower = hl2 - multiplier * atr[i]

            upper_band.append(upper)
            lower_band.append(lower)

        trend = None

        for i in range(len(closes)):

            if upper_band[i] is None:
                continue

            if trend is None:

                trend = lower_band[i]

            elif closes[i] > trend:

                trend = lower_band[i]

            else:

                trend = upper_band[i]

            result[i] = trend

        return result