class AverageTrueRange:

    @staticmethod
    def atr(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
    ) -> list[float | None]:

        true_ranges: list[float] = []

        for i in range(len(closes)):

            if i == 0:
                tr = highs[i] - lows[i]
            else:
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )

            true_ranges.append(tr)

        atr_values: list[float | None] = []

        for i in range(len(true_ranges)):

            if i + 1 < period:
                atr_values.append(None)
                continue

            window = true_ranges[i + 1 - period : i + 1]

            atr_values.append(sum(window) / period)

        return atr_values
