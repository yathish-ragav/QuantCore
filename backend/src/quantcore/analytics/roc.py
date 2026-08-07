from typing import List


class RateOfChange:

    @staticmethod
    def calculate(
        closes: List[float],
        period: int = 12,
    ) -> List[float]:

        result = []

        for i in range(len(closes)):

            if i < period:
                result.append(None)
                continue

            previous = closes[i - period]

            if previous == 0:
                result.append(0.0)
                continue

            roc = (
                (closes[i] - previous)
                / previous
            ) * 100

            result.append(roc)

        return result