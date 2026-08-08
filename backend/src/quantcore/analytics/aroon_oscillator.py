from typing import List

from .aroon import Aroon


class AroonOscillator:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        period: int = 25,
    ) -> List[float]:

        aroon_values = Aroon.calculate(
            highs,
            lows,
            period,
        )

        result = []

        for value in aroon_values:

            if (
                value["aroon_up"] is None
                or value["aroon_down"] is None
            ):
                result.append(None)
                continue

            oscillator = (
                value["aroon_up"]
                - value["aroon_down"]
            )

            result.append(oscillator)

        return result