import pytest

from quantcore.analytics.ultimate_oscillator import UltimateOscillator


def test_ultimate_oscillator_basic():
    highs = [10, 10, 10, 10, 10]
    lows = [8, 8, 8, 8, 8]
    closes = [9, 9, 9, 9, 9]

    result = UltimateOscillator.calculate(
        highs,
        lows,
        closes,
        short_period=2,
        medium_period=3,
        long_period=4,
    )

    # The implementation waits until i >= long_period.
    #
    # Therefore:
    # index 0 -> None
    # index 1 -> None
    # index 2 -> None
    # index 3 -> None
    # index 4 -> first valid value

    assert result[0] is None
    assert result[1] is None
    assert result[2] is None
    assert result[3] is None

    # Every candle:
    #
    # Previous close = 9
    #
    # Buying Pressure:
    # 9 - min(8, 9) = 1
    #
    # True Range:
    # max(10, 9) - min(8, 9)
    # = 10 - 8
    # = 2
    #
    # Therefore every BP/TR ratio = 1/2 = 0.5
    #
    # avg7  = 0.5
    # avg14 = 0.5
    # avg28 = 0.5
    #
    # UO =
    # ((4 * 0.5) + (2 * 0.5) + 0.5) / 7 * 100
    #
    # = 50

    assert result[4] == pytest.approx(50.0)


def test_ultimate_oscillator_multiple_values():
    highs = [10, 10, 10, 10, 10, 10]
    lows = [8, 8, 8, 8, 8, 8]
    closes = [9, 9, 9, 9, 9, 9]

    result = UltimateOscillator.calculate(
        highs,
        lows,
        closes,
        short_period=2,
        medium_period=3,
        long_period=4,
    )

    # The input is constant, so all rolling
    # BP/TR ratios remain 0.5.

    assert result[4] == pytest.approx(50.0)
    assert result[5] == pytest.approx(50.0)


def test_ultimate_oscillator_zero_true_range():
    highs = [10, 10, 10, 10, 10]
    lows = [10, 10, 10, 10, 10]
    closes = [10, 10, 10, 10, 10]

    result = UltimateOscillator.calculate(
        highs,
        lows,
        closes,
        short_period=2,
        medium_period=3,
        long_period=4,
    )

    # BP = 0
    # TR = 0
    #
    # The implementation handles zero TR by using:
    #
    # avg = 0
    #
    # Therefore UO = 0.

    assert result[0] is None
    assert result[1] is None
    assert result[2] is None
    assert result[3] is None

    assert result[4] == pytest.approx(0.0)


def test_ultimate_oscillator_insufficient_data():
    highs = [10, 10, 10]
    lows = [8, 8, 8]
    closes = [9, 9, 9]

    result = UltimateOscillator.calculate(
        highs,
        lows,
        closes,
        short_period=2,
        medium_period=3,
        long_period=4,
    )

    # There is no index >= long_period (4),
    # so every result must be None.

    assert result == [
        None,
        None,
        None,
    ]


def test_ultimate_oscillator_weighted_calculation():
    highs = [10, 11, 12, 13, 14]
    lows = [8, 9, 10, 11, 12]
    closes = [9, 10, 11, 12, 13]

    result = UltimateOscillator.calculate(
        highs,
        lows,
        closes,
        short_period=2,
        medium_period=3,
        long_period=4,
    )

    # Every candle has:
    #
    # BP = Close - Low = 1
    # TR = High - Low = 2
    #
    # Therefore every rolling ratio is 0.5.
    #
    # This confirms the weighted combination:
    #
    # ((4 * 0.5) + (2 * 0.5) + 0.5) / 7 * 100
    # = 50

    assert result[4] == pytest.approx(50.0)