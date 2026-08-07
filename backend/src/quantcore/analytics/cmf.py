from typing import List


class ChaikinMoneyFlow:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        period: int = 20,
    ) -> List[float | None]:

        if not (
            len(highs)
            == len(lows)
            == len(closes)
            == len(volumes)
        ):
            raise ValueError("Input lengths must match.")

        money_flow_volume = []

        for high, low, close, volume in zip(
            highs,
            lows,
            closes,
            volumes,
        ):

            if high == low:
                money_flow_volume.append(0.0)
                continue

            multiplier = (
                ((close - low) - (high - close))
                / (high - low)
            )

            money_flow_volume.append(
                multiplier * volume
            )

        cmf_values: List[float | None] = []

        for i in range(len(closes)):

            if i + 1 < period:
                cmf_values.append(None)
                continue

            mfv_sum = sum(
                money_flow_volume[
                    i + 1 - period : i + 1
                ]
            )

            volume_sum = sum(
                volumes[
                    i + 1 - period : i + 1
                ]
            )

            if volume_sum == 0:
                cmf_values.append(None)
                continue

            cmf_values.append(
                mfv_sum / volume_sum
            )

        return cmf_values