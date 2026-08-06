from typing import List, Dict

from .ema import ExponentialMovingAverage


class MACD:

    @staticmethod
    def macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> List[Dict]:

        ema_fast = ExponentialMovingAverage.ema(
            prices,
            fast_period,
        )

        ema_slow = ExponentialMovingAverage.ema(
            prices,
            slow_period,
        )

        macd_line = []

        for fast, slow in zip(ema_fast, ema_slow):

            if fast is None or slow is None:
                macd_line.append(None)

            else:
                macd_line.append(fast - slow)

        # Calculate signal line only from valid MACD values
        valid_macd = [x for x in macd_line if x is not None]

        signal_values = ExponentialMovingAverage.ema(
            valid_macd,
            signal_period,
        )

        signal_full = [None] * len(macd_line)

        index = 0

        for i in range(len(macd_line)):

            if macd_line[i] is not None:
                signal_full[i] = signal_values[index]
                index += 1

        results = []

        for macd, signal in zip(macd_line, signal_full):

            histogram = None

            if macd is not None and signal is not None:
                histogram = macd - signal

            results.append(
                {
                    "macd": macd,
                    "signal": signal,
                    "histogram": histogram,
                }
            )

        return results