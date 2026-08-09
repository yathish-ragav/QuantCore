from typing import List


class CoppockCurve:

    @staticmethod
    def calculate(
        closes: List[float],
        roc_fast_period: int = 14,
        roc_slow_period: int = 11,
        wma_period: int = 10,
    ) -> List[float | None]:

        if (
            roc_fast_period <= 0
            or roc_slow_period <= 0
            or wma_period <= 0
        ):
            raise ValueError(
                "Periods must be greater than zero."
            )

        if not closes:
            return []

        roc_fast = [None] * len(closes)
        roc_slow = [None] * len(closes)

        for i in range(len(closes)):

            if i >= roc_fast_period:
                previous = closes[i - roc_fast_period]

                if previous != 0:
                    roc_fast[i] = (
                        (closes[i] - previous)
                        / previous
                    ) * 100

            if i >= roc_slow_period:
                previous = closes[i - roc_slow_period]

                if previous != 0:
                    roc_slow[i] = (
                        (closes[i] - previous)
                        / previous
                    ) * 100

        roc_sum: List[float | None] = []

        for fast, slow in zip(
            roc_fast,
            roc_slow,
        ):
            if fast is None or slow is None:
                roc_sum.append(None)
            else:
                roc_sum.append(fast + slow)

        result: List[float | None] = []

        weights = list(range(1, wma_period + 1))
        weight_sum = sum(weights)

        for i in range(len(closes)):

            if i + 1 < wma_period:
                result.append(None)
                continue

            window = roc_sum[
                i + 1 - wma_period : i + 1
            ]

            if any(value is None for value in window):
                result.append(None)
                continue

            weighted_sum = sum(
                value * weight
                for value, weight in zip(
                    window,
                    weights,
                )
            )

            result.append(
                weighted_sum / weight_sum
            )

        return result