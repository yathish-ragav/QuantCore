from .atr import AverageTrueRange


class Supertrend:

    @staticmethod
    def calculate(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 10,
        multiplier: float = 3.0,
    ):

        atr = AverageTrueRange.atr(
            highs,
            lows,
            closes,
            period,
        )

        result: list[float | None] = [None] * len(closes)

        upper_band: list[float | None] = []
        lower_band: list[float | None] = []

        for i in range(len(closes)):

            if atr[i] is None:

                upper_band.append(None)
                lower_band.append(None)

                continue

            atr_value = atr[i]
            assert atr_value is not None

            hl2 = (highs[i] + lows[i]) / 2

            upper = hl2 + multiplier * atr_value
            lower = hl2 - multiplier * atr_value

            upper_band.append(upper)
            lower_band.append(lower)

        trend = None

        for i in range(len(closes)):

            if upper_band[i] is None:
                continue

            if trend is None or closes[i] > trend:

                trend = lower_band[i]

            else:

                trend = upper_band[i]

            result[i] = trend

        return result
