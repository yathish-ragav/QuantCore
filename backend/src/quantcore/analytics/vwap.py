class VolumeWeightedAveragePrice:

    @staticmethod
    def calculate(
        highs,
        lows,
        closes,
        volumes,
    ):
        if not (
            len(highs)
            == len(lows)
            == len(closes)
            == len(volumes)
        ):
            raise ValueError(
                "Input lengths must match."
            )

        cumulative_price_volume = 0.0
        cumulative_volume = 0.0

        result = []

        for high, low, close, volume in zip(
            highs,
            lows,
            closes,
            volumes,
        ):

            typical_price = (
                high
                + low
                + close
            ) / 3

            cumulative_price_volume += (
                typical_price * volume
            )

            cumulative_volume += volume

            if cumulative_volume == 0:

                result.append(None)

            else:

                result.append(
                    cumulative_price_volume
                    / cumulative_volume
                )

        return result