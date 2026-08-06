class ParabolicSAR:

    @staticmethod
    def calculate(
        highs,
        lows,
        step=0.02,
        max_step=0.2,
    ):
        if len(highs) != len(lows):
            raise ValueError(
                "High and Low lengths must match."
            )

        if len(highs) == 0:
            return []

        psar = [None] * len(highs)

        bull = True

        af = step

        ep = highs[0]

        sar = lows[0]

        psar[0] = None

        for i in range(1, len(highs)):

            sar = sar + af * (ep - sar)

            if bull:

                sar = min(
                    sar,
                    lows[i - 1],
                )

                if i > 1:
                    sar = min(
                        sar,
                        lows[i - 2],
                    )

                if lows[i] < sar:

                    bull = False

                    sar = ep

                    ep = lows[i]

                    af = step

                else:

                    if highs[i] > ep:

                        ep = highs[i]

                        af = min(
                            af + step,
                            max_step,
                        )

            else:

                sar = max(
                    sar,
                    highs[i - 1],
                )

                if i > 1:
                    sar = max(
                        sar,
                        highs[i - 2],
                    )

                if highs[i] > sar:

                    bull = True

                    sar = ep

                    ep = highs[i]

                    af = step

                else:

                    if lows[i] < ep:

                        ep = lows[i]

                        af = min(
                            af + step,
                            max_step,
                        )

            psar[i] = sar

        return psar