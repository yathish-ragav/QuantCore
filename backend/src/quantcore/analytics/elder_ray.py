class ElderRayIndex:

    @staticmethod
    def calculate(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 13,
    ) -> list[dict]:

        if not (len(highs) == len(lows) == len(closes)):
            raise ValueError("Input lengths must match.")

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        ema_values: list[float | None] = []

        if len(closes) < period:
            ema_values = [None] * len(closes)
        else:
            multiplier = 2 / (period + 1)

            initial_ema = sum(closes[:period]) / period

            ema_values.extend([None] * (period - 1))
            ema_values.append(initial_ema)

            previous_ema = initial_ema

            for close in closes[period:]:
                current_ema = (close - previous_ema) * multiplier + previous_ema

                ema_values.append(current_ema)
                previous_ema = current_ema

        result: list[dict] = []

        for high, low, ema in zip(highs, lows, ema_values, strict=True):
            if ema is None:
                result.append(
                    {
                        "bull_power": None,
                        "bear_power": None,
                    }
                )
            else:
                result.append(
                    {
                        "bull_power": high - ema,
                        "bear_power": low - ema,
                    }
                )

        return result
