class ForceIndex:

    @staticmethod
    def force_index(
        closes: list[float],
        volumes: list[float],
    ) -> list[float | None]:

        result: list[float | None] = [None]

        for i in range(1, len(closes)):
            force = (closes[i] - closes[i - 1]) * volumes[i]
            result.append(force)

        return result
