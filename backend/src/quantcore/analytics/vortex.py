from typing import List


class VortexIndicator:

    @staticmethod
    def calculate(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> List[dict]:

        if not (
            len(highs)
            == len(lows)
            == len(closes)
        ):
            raise ValueError(
                "Input lengths must match."
            )

        if period <= 0:
            raise ValueError(
                "Period must be greater than zero."
            )

        result = []

        true_ranges = []
        positive_vm = []
        negative_vm = []

        for i in range(len(closes)):

            if i == 0:
                true_ranges.append(None)
                positive_vm.append(None)
                negative_vm.append(None)
                continue

            true_range = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )

            vm_plus = abs(
                highs[i] - lows[i - 1]
            )

            vm_minus = abs(
                lows[i] - highs[i - 1]
            )

            true_ranges.append(true_range)
            positive_vm.append(vm_plus)
            negative_vm.append(vm_minus)

        for i in range(len(closes)):

            if i < period:
                result.append(
                    {
                        "vortex_plus": None,
                        "vortex_minus": None,
                    }
                )
                continue

            tr_window = true_ranges[
                i - period + 1 : i + 1
            ]

            vm_plus_window = positive_vm[
                i - period + 1 : i + 1
            ]

            vm_minus_window = negative_vm[
                i - period + 1 : i + 1
            ]

            tr_sum = sum(
                value
                for value in tr_window
                if value is not None
            )

            vm_plus_sum = sum(
                value
                for value in vm_plus_window
                if value is not None
            )

            vm_minus_sum = sum(
                value
                for value in vm_minus_window
                if value is not None
            )

            if tr_sum == 0:
                result.append(
                    {
                        "vortex_plus": None,
                        "vortex_minus": None,
                    }
                )
                continue

            vortex_plus = (
                vm_plus_sum / tr_sum
            )

            vortex_minus = (
                vm_minus_sum / tr_sum
            )

            result.append(
                {
                    "vortex_plus": vortex_plus,
                    "vortex_minus": vortex_minus,
                }
            )

        return result