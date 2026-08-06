from typing import List


class RelativeStrengthIndex:

    @staticmethod
    def rsi(
        prices: List[float],
        period: int = 14,
    ) -> List[float | None]:

        if len(prices) < period + 1:
            return [None] * len(prices)

        gains = []
        losses = []

        rsi_values = [None]

        for i in range(1, len(prices)):

            change = prices[i] - prices[i - 1]

            gains.append(max(change, 0))

            losses.append(abs(min(change, 0)))

            if i < period:
                rsi_values.append(None)
                continue

            avg_gain = sum(
                gains[-period:]
            ) / period

            avg_loss = sum(
                losses[-period:]
            ) / period

            if avg_loss == 0:
                rsi_values.append(100.0)
                continue

            rs = avg_gain / avg_loss

            rsi = 100 - (
                100 / (1 + rs)
            )

            rsi_values.append(rsi)

        return rsi_values