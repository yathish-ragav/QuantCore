from math import sqrt


class BollingerBands:

    @staticmethod
    def calculate(
        prices: list[float],
        period: int = 20,
        multiplier: float = 2.0,
    ) -> list[dict[str, float | None]]:

        bands: list[dict[str, float | None]] = []

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

            variance = sum((x - sma) ** 2 for x in window) / period

            std = sqrt(variance)

            bands.append(
                {
                    "middle": sma,
                    "upper": sma + multiplier * std,
                    "lower": sma - multiplier * std,
                }
            )

        return bands
