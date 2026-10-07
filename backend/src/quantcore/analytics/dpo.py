class DetrendedPriceOscillator:

    @staticmethod
    def calculate(
        closes: list[float],
        period: int = 20,
    ) -> list[float | None]:

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        result: list[float | None] = []

        displacement = (period // 2) + 1

        for i in range(len(closes)):

            if i < (period - 1 + displacement):
                result.append(None)
                continue

            sma_start = i - period + 1
            sma_end = i + 1

            sma = sum(closes[sma_start:sma_end]) / period

            displaced_close = closes[i - displacement]

            dpo = displaced_close - sma

            result.append(dpo)

        return result
