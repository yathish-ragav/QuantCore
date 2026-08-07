from typing import List


class WilliamsR:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> List[float]:

        if not (
            len(highs)
            == len(lows)
            == len(closes)
        ):
            raise ValueError(
                "Input lengths must match."
            )

        result = []

        for i in range(len(closes)):

            if i < period - 1:
                result.append(None)
                continue

            highest_high = max(
                highs[i - period + 1 : i + 1]
            )

            lowest_low = min(
                lows[i - period + 1 : i + 1]
            )

            denominator = highest_high - lowest_low

            if denominator == 0:
                result.append(0.0)
                continue

            wr = (
                (highest_high - closes[i])
                / denominator
            ) * -100

            result.append(wr)

        return result