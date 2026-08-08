from typing import List


class PositiveVolumeIndex:

    @staticmethod
    def calculate(
        closes: List[float],
        volumes: List[float],
        base_value: float = 1000.0,
    ) -> List[float]:

        if len(closes) != len(volumes):
            raise ValueError("Input lengths must match.")

        if not closes:
            return []

        result = [base_value]

        pvi = base_value

        for i in range(1, len(closes)):

            previous_close = closes[i - 1]

            if previous_close == 0:
                result.append(pvi)
                continue

            if volumes[i] > volumes[i - 1]:

                percentage_change = (
                    (closes[i] - previous_close)
                    / previous_close
                )

                pvi = pvi * (
                    1 + percentage_change
                )

            result.append(pvi)

        return result