class RateOfChange:

    @staticmethod
    def calculate(
        closes: list[float],
        period: int = 12,
    ) -> list[float | None]:

        result: list[float | None] = []

        for i in range(len(closes)):

            if i < period:
                result.append(None)
                continue

            previous = closes[i - period]

            if previous == 0:
                result.append(0.0)
                continue

            roc = ((closes[i] - previous) / previous) * 100

            result.append(roc)

        return result
