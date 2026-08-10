import pytest

from quantcore.analytics.supertrend import Supertrend
from quantcore.analytics.atr import AverageTrueRange


def test_supertrend_basic():
    highs = [10, 12, 14, 16, 18]
    lows = [8, 9, 10, 12, 14]
    closes = [9, 11, 13, 15, 17]

    period = 3
    multiplier = 2.0

    result = Supertrend.calculate(
        highs,
        lows,
        closes,
        period=period,
        multiplier=multiplier,
    )

    atr = AverageTrueRange.atr(
        highs,
        lows,
        closes,
        period,
    )

    # Before ATR becomes available,
    # Supertrend must also be unavailable.
    for i in range(period - 1):
        assert result[i] is None

    # First valid Supertrend value:
    # trend starts as the lower band.
    i = period - 1

    hl2 = (highs[i] + lows[i]) / 2
    expected_lower = hl2 + 0.0 - multiplier * atr[i]

    assert result[i] == pytest.approx(
        expected_lower
    )


def test_supertrend_follows_lower_band_when_close_above_trend():
    highs = [10, 12, 14, 16, 18, 20]
    lows = [8, 9, 10, 12, 14, 16]
    closes = [9, 11, 13, 15, 17, 19]

    period = 3
    multiplier = 2.0

    result = Supertrend.calculate(
        highs,
        lows,
        closes,
        period=period,
        multiplier=multiplier,
    )

    atr = AverageTrueRange.atr(
        highs,
        lows,
        closes,
        period,
    )

    # After the first valid value, the price remains
    # above the previous trend in this rising market.
    # Therefore the implementation selects the
    # current lower band.
    for i in range(period, len(closes)):
        hl2 = (highs[i] + lows[i]) / 2
        expected_lower = (
            hl2 - multiplier * atr[i]
        )

        assert result[i] == pytest.approx(
            expected_lower
        )


def test_supertrend_switches_to_upper_band():
    highs = [10, 12, 14, 16, 15, 14]
    lows = [8, 9, 10, 12, 10, 8]
    closes = [9, 11, 13, 15, 11, 9]

    period = 3
    multiplier = 2.0

    result = Supertrend.calculate(
        highs,
        lows,
        closes,
        period=period,
        multiplier=multiplier,
    )

    atr = AverageTrueRange.atr(
        highs,
        lows,
        closes,
        period,
    )

    # The first valid value initializes trend
    # with the lower band.
    first = period - 1

    hl2_first = (
        highs[first] + lows[first]
    ) / 2

    expected_first = (
        hl2_first - multiplier * atr[first]
    )

    assert result[first] == pytest.approx(
        expected_first
    )

    # Verify that whenever the implementation's
    # condition closes[i] <= previous trend is met,
    # it selects the upper band.
    #
    # We reproduce the exact state transition
    # from the implementation.
    trend = expected_first

    for i in range(period, len(closes)):
        hl2 = (highs[i] + lows[i]) / 2

        upper = (
            hl2 + multiplier * atr[i]
        )

        lower = (
            hl2 - multiplier * atr[i]
        )

        if closes[i] > trend:
            expected = lower
        else:
            expected = upper

        assert result[i] == pytest.approx(
            expected
        )

        trend = expected


def test_supertrend_insufficient_data():
    highs = [10, 12]
    lows = [8, 9]
    closes = [9, 11]

    result = Supertrend.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result == [
        None,
        None,
    ]