from quantcore.analytics.atr import AverageTrueRange


def test_atr_basic():
    highs = [10, 12, 13, 15]
    lows = [8, 9, 10, 12]
    closes = [9, 11, 12, 14]

    result = AverageTrueRange.atr(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result[:2] == [None, None]
    assert result[2] == 8 / 3
    assert result[3] == 3.0


def test_atr_period_larger_than_data():
    highs = [10, 12]
    lows = [8, 9]
    closes = [9, 11]

    result = AverageTrueRange.atr(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result == [None, None]


def test_atr_true_range_uses_previous_close():
    highs = [10, 12, 13]
    lows = [8, 9, 10]
    closes = [9, 20, 12]

    result = AverageTrueRange.atr(
        highs,
        lows,
        closes,
        period=2,
    )

    assert result[0] is None
    assert result[1] == 2.5
    assert result[2] == 6.5