class MovingAverage:

    @staticmethod
    def sma(
        prices: list[float],
        period: int,
    ) -> list[float | None]:

        sma_values: list[float | None] = []

        for i in range(len(prices)):

            if i + 1 < period:
                sma_values.append(None)
                continue

            window = prices[i + 1 - period : i + 1]

            sma_values.append(sum(window) / period)

        return sma_values
