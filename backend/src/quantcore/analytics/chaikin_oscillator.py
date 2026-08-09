from typing import List


class ChaikinOscillator:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        fast_period: int = 3,
        slow_period: int = 10,
    ) -> List[float | None]:

        if not (
            len(highs)
            == len(lows)
            == len(closes)
            == len(volumes)
        ):
            raise ValueError("Input lengths must match.")

        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("Periods must be greater than zero.")

        if fast_period >= slow_period:
            raise ValueError(
                "Fast period must be less than slow period."
            )

        adl = []
        cumulative_adl = 0.0

        for high, low, close, volume in zip(
            highs,
            lows,
            closes,
            volumes,
        ):
            if high == low:
                money_flow_multiplier = 0.0
            else:
                money_flow_multiplier = (
                    ((close - low) - (high - close))
                    / (high - low)
                )

            money_flow_volume = (
                money_flow_multiplier * volume
            )

            cumulative_adl += money_flow_volume
            adl.append(cumulative_adl)

        def ema(
            values: List[float],
            period: int,
        ) -> List[float | None]:

            result: List[float | None] = []

            if len(values) < period:
                return [None] * len(values)

            multiplier = 2 / (period + 1)

            initial = sum(values[:period]) / period
            result.extend([None] * (period - 1))
            result.append(initial)

            previous = initial

            for value in values[period:]:
                current = (
                    (value - previous) * multiplier
                    + previous
                )

                result.append(current)
                previous = current

            return result

        fast_ema = ema(adl, fast_period)
        slow_ema = ema(adl, slow_period)

        result: List[float | None] = []

        for fast, slow in zip(fast_ema, slow_ema):

            if fast is None or slow is None:
                result.append(None)
            else:
                result.append(fast - slow)

        return result