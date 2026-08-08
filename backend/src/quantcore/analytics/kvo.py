from typing import List


class KlingerVolumeOscillator:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        fast_period: int = 34,
        slow_period: int = 55,
        signal_period: int = 13,
    ) -> List[dict]:

        if not (
            len(highs)
            == len(lows)
            == len(closes)
            == len(volumes)
        ):
            raise ValueError("Input lengths must match.")

        if (
            fast_period <= 0
            or slow_period <= 0
            or signal_period <= 0
        ):
            raise ValueError(
                "Periods must be greater than zero."
            )

        if not closes:
            return []

        hlc = [
            high + low + close
            for high, low, close in zip(
                highs,
                lows,
                closes,
            )
        ]

        trend = [None] * len(closes)

        for i in range(1, len(closes)):
            if hlc[i] > hlc[i - 1]:
                trend[i] = 1
            elif hlc[i] < hlc[i - 1]:
                trend[i] = -1
            else:
                trend[i] = trend[i - 1] or 1

        vf = [0.0] * len(closes)

        for i in range(1, len(closes)):
            dm = highs[i] - lows[i]

            if dm == 0:
                vf[i] = 0.0
                continue

            cm = abs(hlc[i] - hlc[i - 1])

            vf[i] = (
                volumes[i]
                * trend[i]
                * abs(2 * (cm / dm) - 1)
            )

        def ema(
            values: List[float],
            period: int,
        ) -> List[float]:

            alpha = 2 / (period + 1)

            result = [values[0]]

            for i in range(1, len(values)):
                result.append(
                    alpha * values[i]
                    + (1 - alpha) * result[-1]
                )

            return result

        fast_ema = ema(vf, fast_period)
        slow_ema = ema(vf, slow_period)

        kvo = [
            fast - slow
            for fast, slow in zip(
                fast_ema,
                slow_ema,
            )
        ]

        signal = ema(
            kvo,
            signal_period,
        )

        result = []

        for i in range(len(closes)):

            if i < slow_period - 1:
                result.append(
                    {
                        "kvo": None,
                        "signal": None,
                    }
                )
                continue

            result.append(
                {
                    "kvo": kvo[i],
                    "signal": signal[i],
                }
            )

        return result