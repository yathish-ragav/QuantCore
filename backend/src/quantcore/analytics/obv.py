class OnBalanceVolume:

    @staticmethod
    def calculate(
        closes,
        volumes,
    ):
        if len(closes) != len(volumes):
            raise ValueError(
                "Input lengths must match."
            )

        if not closes:
            return []

        result = [0]

        obv = 0

        for i in range(1, len(closes)):

            if closes[i] > closes[i - 1]:

                obv += volumes[i]

            elif closes[i] < closes[i - 1]:

                obv -= volumes[i]

            result.append(obv)

        return result