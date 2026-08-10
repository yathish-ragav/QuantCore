import pytest

from quantcore.analytics.chaikin_oscillator import ChaikinOscillator


def test_chaikin_oscillator_basic():
    highs = [10, 12, 14, 16]
    lows = [8, 10, 12, 14]
    closes = [10, 12, 14, 16]
    volumes = [100, 100, 100, 100]

    result = ChaikinOscillator.calculate(
        highs,
        lows,
        closes,
        volumes,
        fast_period=2,
        slow_period=3,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(50.0)
    assert result[3] == pytest.approx(50.0)


def test_chaikin_oscillator_insufficient_data():
    highs = [10, 12]
    lows = [8, 10]
    closes = [10, 12]
    volumes = [100, 100]

    result = ChaikinOscillator.calculate(
        highs,
        lows,
        closes,
        volumes,
        fast_period=2,
        slow_period=3,
    )

    assert result == [
        None,
        None,
    ]


def test_chaikin_oscillator_mismatched_lengths():
    highs = [10, 12, 14]
    lows = [8, 10]
    closes = [10, 12, 14]
    volumes = [100, 100, 100]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        ChaikinOscillator.calculate(
            highs,
            lows,
            closes,
            volumes,
        )


def test_chaikin_oscillator_invalid_periods():
    highs = [10, 12, 14]
    lows = [8, 10, 12]
    closes = [10, 12, 14]
    volumes = [100, 100, 100]

    with pytest.raises(
        ValueError,
        match="Periods must be greater than zero.",
    ):
        ChaikinOscillator.calculate(
            highs,
            lows,
            closes,
            volumes,
            fast_period=0,
            slow_period=3,
        )


def test_chaikin_oscillator_fast_period_must_be_less():
    highs = [10, 12, 14]
    lows = [8, 10, 12]
    closes = [10, 12, 14]
    volumes = [100, 100, 100]

    with pytest.raises(
        ValueError,
        match="Fast period must be less than slow period.",
    ):
        ChaikinOscillator.calculate(
            highs,
            lows,
            closes,
            volumes,
            fast_period=5,
            slow_period=3,
        )