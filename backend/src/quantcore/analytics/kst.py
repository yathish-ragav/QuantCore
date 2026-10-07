class KnowSureThing:
    @staticmethod
    def calculate(
        closes: list[float],
        roc1_period: int = 10,
        roc2_period: int = 15,
        roc3_period: int = 20,
        roc4_period: int = 30,
        sma1_period: int = 10,
        sma2_period: int = 10,
        sma3_period: int = 10,
        sma4_period: int = 15,
    ) -> list[float | None]:
        def roc(period: int) -> list[float | None]:
            values: list[float | None] = []

            for i in range(len(closes)):
                if i < period:
                    values.append(None)
                    continue

                previous = closes[i - period]

                if previous == 0:
                    values.append(None)
                    continue

                values.append(((closes[i] - previous) / previous) * 100)

            return values

        def sma(
            values: list[float | None],
            period: int,
        ) -> list[float | None]:
            result: list[float | None] = []

            for i in range(len(values)):
                if i + 1 < period:
                    result.append(None)
                    continue

                window = values[i + 1 - period : i + 1]

                if any(value is None for value in window):
                    result.append(None)
                    continue

                numeric_window = [value for value in window if value is not None]
                result.append(sum(numeric_window) / period)

            return result

        roc1 = roc(roc1_period)
        roc2 = roc(roc2_period)
        roc3 = roc(roc3_period)
        roc4 = roc(roc4_period)

        sma1 = sma(roc1, sma1_period)
        sma2 = sma(roc2, sma2_period)
        sma3 = sma(roc3, sma3_period)
        sma4 = sma(roc4, sma4_period)

        result: list[float | None] = []

        for i in range(len(closes)):
            sma1_value = sma1[i]
            sma2_value = sma2[i]
            sma3_value = sma3[i]
            sma4_value = sma4[i]

            if (
                sma1_value is None
                or sma2_value is None
                or sma3_value is None
                or sma4_value is None
            ):
                result.append(None)
                continue

            kst_value = sma1_value + 2 * sma2_value + 3 * sma3_value + 4 * sma4_value

            result.append(kst_value)

        return result
