from typing import List


class UltimateOscillator:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        short_period: int = 7,
        medium_period: int = 14,
        long_period: int = 28,
    ) -> List[float]:

        buying_pressure = []
        true_range = []

        for i in range(len(closes)):

            if i == 0:
                previous_close = closes[0]
            else:
                previous_close = closes[i - 1]

            bp = closes[i] - min(lows[i], previous_close)

            tr = max(highs[i], previous_close) - min(
                lows[i],
                previous_close,
            )

            buying_pressure.append(bp)
            true_range.append(tr)

        result = []

        for i in range(len(closes)):

            if i < long_period:
                result.append(None)
                continue

            bp7 = sum(
                buying_pressure[
                    i - short_period + 1 : i + 1
                ]
            )

            tr7 = sum(
                true_range[
                    i - short_period + 1 : i + 1
                ]
            )

            bp14 = sum(
                buying_pressure[
                    i - medium_period + 1 : i + 1
                ]
            )

            tr14 = sum(
                true_range[
                    i - medium_period + 1 : i + 1
                ]
            )

            bp28 = sum(
                buying_pressure[
                    i - long_period + 1 : i + 1
                ]
            )

            tr28 = sum(
                true_range[
                    i - long_period + 1 : i + 1
                ]
            )

            avg7 = bp7 / tr7 if tr7 else 0
            avg14 = bp14 / tr14 if tr14 else 0
            avg28 = bp28 / tr28 if tr28 else 0

            uo = (
                (
                    (4 * avg7)
                    + (2 * avg14)
                    + avg28
                )
                / 7
            ) * 100

            result.append(uo)

        return result