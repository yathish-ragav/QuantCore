from quantcore.analytics.adx import AverageDirectionalIndex


def test_adx_basic():
    highs = [10, 12, 13, 15]
    lows = [8, 9, 10, 12]
    closes = [9, 11, 12, 14]

    result = AverageDirectionalIndex.adx(
        highs,
        lows,
        closes,
        period=2,
    )

    assert result[0] is None
    assert result[1] == 100.0
    assert result[2] == 100.0
    assert result[3] == 100.0


def test_adx_period_larger_than_data():
    highs = [10, 12, 13]
    lows = [8, 9, 10]
    closes = [9, 11, 12]

    result = AverageDirectionalIndex.adx(
        highs,
        lows,
        closes,
        period=5,
    )

    assert result == [None, None, None]


def test_adx_zero_directional_movement():
    highs = [10, 10, 10, 10]
    lows = [8, 8, 8, 8]
    closes = [9, 9, 9, 9]

    result = AverageDirectionalIndex.adx(
        highs,
        lows,
        closes,
        period=2,
    )

    assert result == [None, None, None, None]