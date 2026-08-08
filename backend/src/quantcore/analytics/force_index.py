from typing import List


class ForceIndex:

    @staticmethod
    def force_index(
        closes: List[float],
        volumes: List[float],
    ) -> List[float | None]:

        result = [None]

        for i in range(1, len(closes)):
            force = (closes[i] - closes[i - 1]) * volumes[i]
            result.append(force)

        return result