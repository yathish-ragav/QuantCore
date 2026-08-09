from typing import List


class KnowSureThing:
    @staticmethod
    def calculate(
        closes: List[float],
        roc1_period: int = 10,
        roc2_period: int = 15,
        roc3_period: int = 20,
        roc4_period: int = 30,
        sma1_period: int = 10,
        sma2_period: int = 10,
        sma3_period: int = 10,
        sma4_period: int = 15,
    ) -> List[float | None]:

        def roc(period: int) -> List[float | None]:
            values = []

            for i in range(len(closes)):
                if i < period:
                    values.append(None)
                    continue

                previous = closes[i - period]

                if previous == 0:
                    values.append(None)
                    continue

                values.append(
                    ((closes[i] - previous) / previous) * 100
                )

            return values

        def sma(
            values: List[float | None],
            period: int,
        ) -> List[float | None]:

            result = []

            for i in range(len(values)):
                if i + 1 < period:
                    result.append(None)
                    continue

                window = values[i + 1 - period : i + 1]

                if any(value is None for value in window):
                    result.append(None)
                    continue

                result.append(
                    sum(window) / period
                )

            return result

        roc1 = roc(roc1_period)
        roc2 = roc(roc2_period)
        roc3 = roc(roc3_period)
        roc4 = roc(roc4_period)

        sma1 = sma(roc1, sma1_period)
        sma2 = sma(roc2, sma2_period)
        sma3 = sma(roc3, sma3_period)
        sma4 = sma(roc4, sma4_period)

        result: List[float | None] = []

        for i in range(len(closes)):

            if (
                sma1[i] is None
                or sma2[i] is None
                or sma3[i] is None
                or sma4[i] is None
            ):
                result.append(None)
                continue

            kst_value = (
                sma1[i]
                + 2 * sma2[i]
                + 3 * sma3[i]
                + 4 * sma4[i]
            )

            result.append(kst_value)

        return result