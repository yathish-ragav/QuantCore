class ExponentialMovingAverage:

    @staticmethod
    def ema(
        prices: list[float],
        period: int,
    ) -> list[float | None]:

        ema_values: list[float | None] = []

        multiplier = 2 / (period + 1)

        sma = None

        for i in range(len(prices)):

            if i + 1 < period:
                ema_values.append(None)
                continue

            if i + 1 == period:
                sma = sum(prices[:period]) / period
                ema_values.append(sma)
                continue

            assert sma is not None
            sma = (prices[i] - sma) * multiplier + sma
            ema_values.append(sma)

        return ema_values
