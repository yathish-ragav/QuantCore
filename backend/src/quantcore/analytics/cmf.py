class ChaikinMoneyFlow:

    @staticmethod
    def calculate(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
        period: int = 20,
    ) -> list[float | None]:

        if not (len(highs) == len(lows) == len(closes) == len(volumes)):
            raise ValueError("Input lengths must match.")

        money_flow_volume = []

        for high, low, close, volume in zip(highs, lows, closes, volumes, strict=True):

            if high == low:
                money_flow_volume.append(0.0)
                continue

            multiplier = ((close - low) - (high - close)) / (high - low)

            money_flow_volume.append(multiplier * volume)

        cmf_values: list[float | None] = []

        for i in range(len(closes)):

            if i + 1 < period:
                cmf_values.append(None)
                continue

            mfv_sum = sum(money_flow_volume[i + 1 - period : i + 1])

            volume_sum = sum(volumes[i + 1 - period : i + 1])

            if volume_sum == 0:
                cmf_values.append(None)
                continue

            cmf_values.append(mfv_sum / volume_sum)

        return cmf_values
