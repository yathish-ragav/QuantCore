from typing import List


class StochasticOscillator:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
        signal_period: int = 3,
    ):

        k_values: List[float | None] = []

        for i in range(len(closes)):

            if i + 1 < period:
                k_values.append(None)
                continue

            highest_high = max(
                highs[i + 1 - period : i + 1]
            )

            lowest_low = min(
                lows[i + 1 - period : i + 1]
            )

            if highest_high == lowest_low:
                k_values.append(0.0)
                continue

            k = (
                (
                    closes[i] - lowest_low
                )
                /
                (
                    highest_high - lowest_low
                )
            ) * 100

            k_values.append(k)

        d_values: List[float | None] = []

        for i in range(len(k_values)):

            if (
                k_values[i] is None
                or i + 1 < signal_period
            ):
                d_values.append(None)
                continue

            window = k_values[
                i + 1 - signal_period : i + 1
            ]

            if any(v is None for v in window):
                d_values.append(None)
                continue

            d_values.append(
                sum(window) / signal_period
            )

        result = []

        for k, d in zip(
            k_values,
            d_values,
        ):

            result.append(
                {
                    "k": k,
                    "d": d,
                }
            )

        return result