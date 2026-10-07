from .atr import AverageTrueRange


class AverageDirectionalIndex:

    @staticmethod
    def adx(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
    ) -> list[float | None]:

        plus_dm = [0.0]
        minus_dm = [0.0]

        for i in range(1, len(highs)):

            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]

            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)

            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

        atr = AverageTrueRange.atr(
            highs,
            lows,
            closes,
            period,
        )

        plus_di: list[float | None] = []
        minus_di: list[float | None] = []

        for i in range(len(atr)):

            if atr[i] is None or atr[i] == 0:

                plus_di.append(None)
                minus_di.append(None)
                continue

            plus_window = plus_dm[i + 1 - period : i + 1]

            minus_window = minus_dm[i + 1 - period : i + 1]

            atr_value = atr[i]
            assert atr_value is not None

            plus = sum(plus_window) / atr_value

            minus = sum(minus_window) / atr_value

            plus_di.append(plus)
            minus_di.append(minus)

        adx_values: list[float | None] = []

        for p, m in zip(plus_di, minus_di, strict=True):

            if p is None or m is None or (p + m) == 0:
                adx_values.append(None)
                continue

            dx = (abs(p - m) / (p + m)) * 100

            adx_values.append(dx)

        return adx_values
