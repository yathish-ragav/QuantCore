from math import sqrt
from typing import List


class BollingerBands:

    @staticmethod
    def calculate(
        prices: List[float],
        period: int = 20,
        multiplier: float = 2.0,
    ):

        bands = []

        for i in range(len(prices)):

            if i + 1 < period:
                bands.append(
                    {
                        "middle": None,
                        "upper": None,
                        "lower": None,
                    }
                )
                continue

            window = prices[i + 1 - period : i + 1]

            sma = sum(window) / period

            variance = sum(
                (x - sma) ** 2
                for x in window
            ) / period

            std = sqrt(variance)

            bands.append(
                {
                    "middle": sma,
                    "upper": sma + multiplier * std,
                    "lower": sma - multiplier * std,
                }
            )

        return bands