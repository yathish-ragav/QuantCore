class RelativeVigorIndex:

    @staticmethod
    def calculate(
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 10,
    ) -> list[float | None]:

        if not (len(opens) == len(highs) == len(lows) == len(closes)):
            raise ValueError("Input lengths must match.")

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        numerator = []
        denominator = []

        for open_, high, low, close in zip(opens, highs, lows, closes, strict=True):
            numerator.append(close - open_)
            denominator.append(high - low)

        result: list[float | None] = []

        for i in range(len(closes)):

            if i + 1 < period:
                result.append(None)
                continue

            numerator_sum = sum(numerator[i + 1 - period : i + 1])

            denominator_sum = sum(denominator[i + 1 - period : i + 1])

            if denominator_sum == 0:
                result.append(None)
                continue

            result.append(numerator_sum / denominator_sum)

        return result
