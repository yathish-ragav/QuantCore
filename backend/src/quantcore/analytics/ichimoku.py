from typing import List


class IchimokuCloud:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
    ) -> List[dict]:

        if len(highs) != len(lows):
            raise ValueError(
                "Input lengths must match."
            )

        results = []

        for i in range(len(highs)):

            tenkan = None
            kijun = None
            span_a = None
            span_b = None

            if i >= 8:

                highest = max(
                    highs[i - 8:i + 1]
                )

                lowest = min(
                    lows[i - 8:i + 1]
                )

                tenkan = (
                    highest + lowest
                ) / 2

            if i >= 25:

                highest = max(
                    highs[i - 25:i + 1]
                )

                lowest = min(
                    lows[i - 25:i + 1]
                )

                kijun = (
                    highest + lowest
                ) / 2

            if (
                tenkan is not None
                and kijun is not None
            ):
                span_a = (
                    tenkan + kijun
                ) / 2

            if i >= 51:

                highest = max(
                    highs[i - 51:i + 1]
                )

                lowest = min(
                    lows[i - 51:i + 1]
                )

                span_b = (
                    highest + lowest
                ) / 2

            results.append(
                {
                    "tenkan": tenkan,
                    "kijun": kijun,
                    "span_a": span_a,
                    "span_b": span_b,
                }
            )

        return results