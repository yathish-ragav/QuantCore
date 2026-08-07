from typing import List

from .ema import ExponentialMovingAverage
from .atr import AverageTrueRange


class KeltnerChannels:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 20,
        multiplier: float = 2.0,
    ) -> List[dict]:

        if not (
            len(highs)
            == len(lows)
            == len(closes)
        ):
            raise ValueError(
                "Input lengths must match."
            )

        ema = ExponentialMovingAverage.ema(
            closes,
            period,
        )

        atr = AverageTrueRange.atr(
            highs,
            lows,
            closes,
            period,
        )

        results = []

        for ema_value, atr_value in zip(
            ema,
            atr,
        ):

            if (
                ema_value is None
                or atr_value is None
            ):

                results.append(
                    {
                        "middle": None,
                        "upper": None,
                        "lower": None,
                    }
                )

                continue

            results.append(
                {
                    "middle": ema_value,
                    "upper": ema_value + multiplier * atr_value,
                    "lower": ema_value - multiplier * atr_value,
                }
            )

        return results