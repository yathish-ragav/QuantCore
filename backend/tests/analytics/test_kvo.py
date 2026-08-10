import pytest

from quantcore.analytics.kvo import KlingerVolumeOscillator


def test_kvo_basic():
    highs = [10, 12, 13, 14, 13]
    lows = [8, 9, 10, 11, 10]
    closes = [9, 11, 12, 13, 11]
    volumes = [100, 200, 300, 400, 500]

    result = KlingerVolumeOscillator.calculate(
        highs,
        lows,
        closes,
        volumes,
        fast_period=2,
        slow_period=3,
        signal_period=2,
    )

    # Output is suppressed until slow_period - 1.
    assert result[0] == {
        "kvo": None,
        "signal": None,
    }

    assert result[1] == {
        "kvo": None,
        "signal": None,
    }

    # Volume Force values:
    #
    # index 0 = 0
    # index 1 = 466.666666...
    # index 2 = 300
    # index 3 = 400
    # index 4 = -833.333333...
    #
    # Fast EMA (period 2):
    # index 2 = 303.703703...
    #
    # Slow EMA (period 3):
    # index 2 = 266.666666...
    #
    # KVO = fast EMA - slow EMA
    #
    # KVO[2] = 37.037037...

    assert result[2]["kvo"] == pytest.approx(
        37.0370370370
    )

    # Signal EMA uses the complete KVO series.
    #
    # KVO:
    # index 0 = 0
    # index 1 = 77.777777...
    # index 2 = 37.037037...
    #
    # Signal EMA period = 2
    #
    # Signal[0] = 0
    #
    # Signal[1] =
    # (2/3 * 77.777777...) + (1/3 * 0)
    # = 51.851851...
    #
    # Signal[2] =
    # (2/3 * 37.037037...)
    # + (1/3 * 51.851851...)
    # = 41.975308...

    assert result[2]["signal"] == pytest.approx(
        41.97530864197529
    )


def test_kvo_trend_reversal():
    highs = [10, 12, 13, 14, 13]
    lows = [8, 9, 10, 11, 10]
    closes = [9, 11, 12, 13, 11]
    volumes = [100, 200, 300, 400, 500]

    result = KlingerVolumeOscillator.calculate(
        highs,
        lows,
        closes,
        volumes,
        fast_period=2,
        slow_period=3,
        signal_period=2,
    )

    # The final HLC is lower than the previous HLC,
    # so the trend becomes negative.
    #
    # This produces negative volume force and causes
    # the KVO to fall.

    assert result[4]["kvo"] < result[3]["kvo"]

    assert result[4]["signal"] < result[3]["signal"]


def test_kvo_zero_daily_range():
    highs = [10, 10, 12]
    lows = [10, 10, 10]
    closes = [10, 10, 11]
    volumes = [100, 200, 300]

    result = KlingerVolumeOscillator.calculate(
        highs,
        lows,
        closes,
        volumes,
        fast_period=2,
        slow_period=3,
        signal_period=2,
    )

    # The first two values are suppressed because
    # slow_period = 3.

    assert result[0] == {
        "kvo": None,
        "signal": None,
    }

    assert result[1] == {
        "kvo": None,
        "signal": None,
    }

    # Zero daily range is handled safely by the
    # implementation and should not raise an error.

    assert result[2]["kvo"] is not None
    assert result[2]["signal"] is not None


def test_kvo_empty_input():
    result = KlingerVolumeOscillator.calculate(
        [],
        [],
        [],
        [],
    )

    assert result == []


def test_kvo_mismatched_input_lengths():
    highs = [10, 12, 13]
    lows = [8, 9]
    closes = [9, 11, 12]
    volumes = [100, 200, 300]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        KlingerVolumeOscillator.calculate(
            highs,
            lows,
            closes,
            volumes,
            fast_period=2,
            slow_period=3,
            signal_period=2,
        )


def test_kvo_invalid_period():
    highs = [10, 12, 13]
    lows = [8, 9, 10]
    closes = [9, 11, 12]
    volumes = [100, 200, 300]

    with pytest.raises(
        ValueError,
        match="Periods must be greater than zero.",
    ):
        KlingerVolumeOscillator.calculate(
            highs,
            lows,
            closes,
            volumes,
            fast_period=0,
            slow_period=3,
            signal_period=2,
        )