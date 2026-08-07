from typing import List


class DonchianChannels:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        period: int = 20,
    ) -> List[dict]:

        if len(highs) != len(lows):
            raise ValueError(
                "Input lengths must match."
            )

        channels = []

        for i in range(len(highs)):

            if i + 1 < period:

                channels.append(
                    {
                        "upper": None,
                        "middle": None,
                        "lower": None,
                    }
                )

                continue

            highest = max(
                highs[
                    i + 1 - period : i + 1
                ]
            )

            lowest = min(
                lows[
                    i + 1 - period : i + 1
                ]
            )

            middle = (
                highest + lowest
            ) / 2

            channels.append(
                {
                    "upper": highest,
                    "middle": middle,
                    "lower": lowest,
                }
            )

        return channels