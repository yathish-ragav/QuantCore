from typing import List


class DetrendedPriceOscillator:

    @staticmethod
    def calculate(
        closes: List[float],
        period: int = 20,
    ) -> List[float]:

        if period <= 0:
            raise ValueError(
                "Period must be greater than zero."
            )

        result = []

        displacement = (period // 2) + 1

        for i in range(len(closes)):

            if i < (period - 1 + displacement):
                result.append(None)
                continue

            sma_start = i - period + 1
            sma_end = i + 1

            sma = sum(
                closes[sma_start:sma_end]
            ) / period

            displaced_close = closes[
                i - displacement
            ]

            dpo = displaced_close - sma

            result.append(dpo)

        return result