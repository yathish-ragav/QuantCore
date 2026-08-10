import pytest

from quantcore.analytics.cci import CommodityChannelIndex


def test_cci_basic():
    highs = [11, 13, 15]
    lows = [9, 11, 13]
    closes = [10, 12, 14]

    result = CommodityChannelIndex.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    # Typical prices = [10, 12, 14]
    # SMA = 12
    # Mean deviation = (2 + 0 + 2) / 3 = 4/3
    # CCI = (14 - 12) / (0.015 * 4/3) = 100
    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(100.0)


def test_cci_period_larger_than_data():
    highs = [11, 13]
    lows = [9, 11]
    closes = [10, 12]

    result = CommodityChannelIndex.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result == [None, None]


def test_cci_zero_mean_deviation():
    highs = [10, 10, 10]
    lows = [10, 10, 10]
    closes = [10, 10, 10]

    result = CommodityChannelIndex.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result == [None, None, 0.0]


def test_cci_mismatched_input_lengths():
    highs = [11, 13, 15]
    lows = [9, 11]
    closes = [10, 12, 14]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        CommodityChannelIndex.calculate(
            highs,
            lows,
            closes,
            period=3,
        )