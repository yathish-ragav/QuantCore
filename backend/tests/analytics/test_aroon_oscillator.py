import pytest

from quantcore.analytics.aroon_oscillator import AroonOscillator


def test_aroon_oscillator_basic():
    highs = [10, 12, 11, 13]
    lows = [8, 9, 7, 10]

    result = AroonOscillator.calculate(
        highs,
        lows,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None

    assert result[2] == pytest.approx(
        66.6666666667 - 100.0
    )

    assert result[3] == pytest.approx(
        100.0 - 66.6666666667
    )


def test_aroon_oscillator_period_larger_than_data():
    highs = [10, 12, 11]
    lows = [8, 9, 7]

    result = AroonOscillator.calculate(
        highs,
        lows,
        period=5,
    )

    assert result == [
        None,
        None,
        None,
    ]


def test_aroon_oscillator_constant_prices():
    highs = [10, 10, 10, 10]
    lows = [8, 8, 8, 8]

    result = AroonOscillator.calculate(
        highs,
        lows,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None

    # When highs and lows are constant, the first
    # occurrence remains the selected extreme.
    assert result[2] == pytest.approx(0.0)
    assert result[3] == pytest.approx(0.0)