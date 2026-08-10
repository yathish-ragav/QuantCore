import pytest

from quantcore.analytics.williams_r import WilliamsR


def test_williams_r_basic():
    highs = [10, 12, 14, 16]
    lows = [0, 2, 4, 6]
    closes = [5, 10, 12, 14]

    result = WilliamsR.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None

    # Index 2:
    # Highest high = 14
    # Lowest low = 0
    # Close = 12
    #
    # Williams %R =
    # (14 - 12) / (14 - 0) * -100
    # = -14.2857...
    assert result[2] == pytest.approx(
        -14.2857142857
    )

    # Index 3:
    # Highest high = 16
    # Lowest low = 2
    # Close = 14
    #
    # = (16 - 14) / (16 - 2) * -100
    # = -14.2857...
    assert result[3] == pytest.approx(
        -14.2857142857
    )


def test_williams_r_period_larger_than_data():
    highs = [10, 12]
    lows = [0, 2]
    closes = [5, 10]

    result = WilliamsR.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result == [
        None,
        None,
    ]


def test_williams_r_zero_range():
    highs = [10, 10, 10]
    lows = [10, 10, 10]
    closes = [10, 10, 10]

    result = WilliamsR.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None

    # highest_high == lowest_low
    # Implementation returns 0.0
    assert result[2] == pytest.approx(0.0)


def test_williams_r_mismatched_input_lengths():
    highs = [10, 12, 14]
    lows = [0, 2]
    closes = [5, 10, 12]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        WilliamsR.calculate(
            highs,
            lows,
            closes,
            period=3,
        )