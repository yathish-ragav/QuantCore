import pytest

from quantcore.analytics.keltner import KeltnerChannels


def test_keltner_basic():
    highs = [10, 12, 13, 15]
    lows = [8, 9, 10, 12]
    closes = [9, 11, 12, 14]

    result = KeltnerChannels.calculate(
        highs,
        lows,
        closes,
        period=3,
        multiplier=2.0,
    )

    # EMA period = 3
    # Initial EMA = (9 + 11 + 12) / 3
    #             = 10.666666...
    #
    # ATR period = 3
    # ATR at index 2 = 8 / 3
    #
    # Upper = EMA + 2 * ATR
    # Lower = EMA - 2 * ATR

    assert result[0] == {
        "middle": None,
        "upper": None,
        "lower": None,
    }

    assert result[1] == {
        "middle": None,
        "upper": None,
        "lower": None,
    }

    assert result[2]["middle"] == pytest.approx(
        10.6666666667
    )

    assert result[2]["upper"] == pytest.approx(
        16.0
    )

    assert result[2]["lower"] == pytest.approx(
        5.3333333333
    )

    # Next EMA:
    # EMA = (14 - 10.666666...) * 0.5
    #       + 10.666666...
    #     = 12.333333...
    #
    # ATR = 3
    #
    # Upper = 12.333333... + 6
    # Lower = 12.333333... - 6

    assert result[3]["middle"] == pytest.approx(
        12.3333333333
    )

    assert result[3]["upper"] == pytest.approx(
        18.3333333333
    )

    assert result[3]["lower"] == pytest.approx(
        6.3333333333
    )


def test_keltner_period_larger_than_data():
    highs = [10, 12]
    lows = [8, 9]
    closes = [9, 11]

    result = KeltnerChannels.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result == [
        {
            "middle": None,
            "upper": None,
            "lower": None,
        },
        {
            "middle": None,
            "upper": None,
            "lower": None,
        },
    ]


def test_keltner_mismatched_input_lengths():
    highs = [10, 12, 13]
    lows = [8, 9]
    closes = [9, 11, 12]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        KeltnerChannels.calculate(
            highs,
            lows,
            closes,
            period=3,
        )