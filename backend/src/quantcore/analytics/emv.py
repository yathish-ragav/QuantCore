class EaseOfMovement:

    @staticmethod
    def emv(
        highs: list[float],
        lows: list[float],
        volumes: list[float],
        period: int = 14,
    ) -> list[float | None]:

        if not (len(highs) == len(lows) == len(volumes)):
            raise ValueError("Input lengths must match.")

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        result: list[float | None] = [None] * len(highs)

        raw_emv: list[float | None] = [None] * len(highs)

        for i in range(1, len(highs)):

            midpoint_move = (highs[i] + lows[i]) / 2 - (highs[i - 1] + lows[i - 1]) / 2

            price_range = highs[i] - lows[i]

            if price_range == 0 or volumes[i] == 0:
                raw_emv[i] = None
                continue

            box_ratio = volumes[i] / price_range

            raw_emv[i] = midpoint_move / box_ratio

        for i in range(period, len(highs)):

            window = raw_emv[i - period + 1 : i + 1]

            if any(value is None for value in window):
                result[i] = None
            else:
                numeric_window = [value for value in window if value is not None]
                result[i] = sum(numeric_window) / period

        return result
