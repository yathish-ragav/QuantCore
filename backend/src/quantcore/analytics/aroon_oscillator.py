from .aroon import Aroon


class AroonOscillator:

    @staticmethod
    def calculate(
        highs: list[float],
        lows: list[float],
        period: int = 25,
    ) -> list[float | None]:

        aroon_values = Aroon.calculate(
            highs,
            lows,
            period,
        )

        result: list[float | None] = []

        for value in aroon_values:

            if value["aroon_up"] is None or value["aroon_down"] is None:
                result.append(None)
                continue

            oscillator = value["aroon_up"] - value["aroon_down"]

            result.append(oscillator)

        return result
