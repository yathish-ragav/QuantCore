from typing import List


class MoneyFlowIndex:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        period: int = 14,
    ) -> List[float | None]:

        if not (
            len(highs)
            == len(lows)
            == len(closes)
            == len(volumes)
        ):
            raise ValueError(
                "Input lengths must match."
            )

        typical_prices = []

        for high, low, close in zip(
            highs,
            lows,
            closes,
        ):
            typical_prices.append(
                (high + low + close) / 3
            )

        positive_flow = [0.0]
        negative_flow = [0.0]

        for i in range(1, len(typical_prices)):

            money_flow = (
                typical_prices[i]
                * volumes[i]
            )

            if (
                typical_prices[i]
                > typical_prices[i - 1]
            ):
                positive_flow.append(
                    money_flow
                )
                negative_flow.append(0.0)

            elif (
                typical_prices[i]
                < typical_prices[i - 1]
            ):
                positive_flow.append(0.0)
                negative_flow.append(
                    money_flow
                )

            else:
                positive_flow.append(0.0)
                negative_flow.append(0.0)

        mfi_values: List[float | None] = []

        for i in range(len(closes)):

            if i + 1 < period:

                mfi_values.append(None)

                continue

            pos_sum = sum(
                positive_flow[
                    i + 1 - period : i + 1
                ]
            )

            neg_sum = sum(
                negative_flow[
                    i + 1 - period : i + 1
                ]
            )

            if neg_sum == 0:

                mfi_values.append(100.0)

                continue

            money_ratio = (
                pos_sum / neg_sum
            )

            mfi = (
                100
                - (
                    100
                    / (1 + money_ratio)
                )
            )

            mfi_values.append(mfi)

        return mfi_values