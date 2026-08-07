from typing import List


class CommodityChannelIndex:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 20,
    ) -> List[float]:

        if not (
            len(highs)
            == len(lows)
            == len(closes)
        ):
            raise ValueError("Input lengths must match.")

        typical_prices = [
            (h + l + c) / 3
            for h, l, c in zip(highs, lows, closes)
        ]

        result = []

        for i in range(len(typical_prices)):

            if i < period - 1:
                result.append(None)
                continue

            window = typical_prices[
                i - period + 1 : i + 1
            ]

            sma = sum(window) / period

            mean_deviation = (
                sum(
                    abs(tp - sma)
                    for tp in window
                )
                / period
            )

            if mean_deviation == 0:
                result.append(0.0)
                continue

            cci = (
                (typical_prices[i] - sma)
                / (0.015 * mean_deviation)
            )

            result.append(cci)

        return result