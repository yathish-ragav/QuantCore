class TRIX:

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float]:

        ema = []
        multiplier = 2 / (period + 1)

        for i, value in enumerate(values):

            if i == 0:
                ema.append(value)
            else:
                ema.append((value - ema[-1]) * multiplier + ema[-1])

        return ema

    @staticmethod
    def calculate(
        closes: list[float],
        period: int = 15,
    ) -> list[float | None]:

        ema1 = TRIX._ema(closes, period)
        ema2 = TRIX._ema(ema1, period)
        ema3 = TRIX._ema(ema2, period)

        result: list[float | None] = [None]

        for i in range(1, len(ema3)):

            previous = ema3[i - 1]

            if previous == 0:
                result.append(0.0)
                continue

            trix = ((ema3[i] - previous) / previous) * 100

            result.append(trix)

        return result
