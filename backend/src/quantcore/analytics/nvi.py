from typing import List


class NegativeVolumeIndex:

    @staticmethod
    def calculate(
        closes: List[float],
        volumes: List[float],
        base_value: float = 1000.0,
    ) -> List[float | None]:

        if len(closes) != len(volumes):
            raise ValueError("Input lengths must match.")

        if not closes:
            return []

        result = [base_value]

        nvi = base_value

        for i in range(1, len(closes)):

            previous_close = closes[i - 1]

            if previous_close == 0:
                result.append(nvi)
                continue

            if volumes[i] < volumes[i - 1]:

                percentage_change = (
                    (closes[i] - previous_close)
                    / previous_close
                )

                nvi = nvi * (
                    1 + percentage_change
                )

            result.append(nvi)

        return result