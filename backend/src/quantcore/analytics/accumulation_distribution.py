class AccumulationDistribution:

    @staticmethod
    def ad(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> list[float | None]:

        if not (len(highs) == len(lows) == len(closes) == len(volumes)):
            raise ValueError("Input lengths must match.")

        result: list[float | None] = [None] * len(closes)

        ad_value = 0.0

        for i in range(len(closes)):

            price_range = highs[i] - lows[i]

            if price_range == 0:
                money_flow_multiplier = 0.0
            else:
                money_flow_multiplier = (
                    (closes[i] - lows[i]) - (highs[i] - closes[i])
                ) / price_range

            money_flow_volume = money_flow_multiplier * volumes[i]

            ad_value += money_flow_volume

            result[i] = ad_value

        return result
