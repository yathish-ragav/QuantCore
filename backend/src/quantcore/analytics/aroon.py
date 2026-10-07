class Aroon:

    @staticmethod
    def calculate(
        highs: list[float],
        lows: list[float],
        period: int = 25,
    ) -> list[dict[str, float | None]]:

        if len(highs) != len(lows):
            raise ValueError("Input lengths must match.")

        result: list[dict[str, float | None]] = []

        for i in range(len(highs)):

            if i < period - 1:
                result.append(
                    {
                        "aroon_up": None,
                        "aroon_down": None,
                    }
                )
                continue

            high_window = highs[i - period + 1 : i + 1]

            low_window = lows[i - period + 1 : i + 1]

            highest_index = high_window.index(max(high_window))

            lowest_index = low_window.index(min(low_window))

            days_since_high = period - 1 - highest_index

            days_since_low = period - 1 - lowest_index

            aroon_up = ((period - days_since_high) / period) * 100

            aroon_down = ((period - days_since_low) / period) * 100

            result.append(
                {
                    "aroon_up": aroon_up,
                    "aroon_down": aroon_down,
                }
            )

        return result
