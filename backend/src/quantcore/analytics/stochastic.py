class StochasticOscillator:

    @staticmethod
    def calculate(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
        signal_period: int = 3,
    ) -> list[dict[str, float | None]]:

        k_values: list[float | None] = []

        for i in range(len(closes)):

            if i + 1 < period:
                k_values.append(None)
                continue

            highest_high = max(highs[i + 1 - period : i + 1])

            lowest_low = min(lows[i + 1 - period : i + 1])

            if highest_high == lowest_low:
                k_values.append(0.0)
                continue

            k = ((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100

            k_values.append(k)

        d_values: list[float | None] = []

        for i in range(len(k_values)):

            if k_values[i] is None or i + 1 < signal_period:
                d_values.append(None)
                continue

            window = k_values[i + 1 - signal_period : i + 1]

            if any(v is None for v in window):
                d_values.append(None)
                continue

            numeric_window = [value for value in window if value is not None]
            d_values.append(sum(numeric_window) / signal_period)

        result: list[dict[str, float | None]] = []

        for k_value, d_value in zip(k_values, d_values, strict=True):

            result.append(
                {
                    "k": k_value,
                    "d": d_value,
                }
            )

        return result
