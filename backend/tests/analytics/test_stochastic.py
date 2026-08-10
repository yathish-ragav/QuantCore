import pytest

from quantcore.analytics.stochastic import StochasticOscillator


def test_stochastic_basic():
    highs = [10, 12, 14, 16, 18]
    lows = [0, 2, 4, 6, 8]
    closes = [5, 10, 12, 14, 16]

    result = StochasticOscillator.calculate(
        highs,
        lows,
        closes,
        period=3,
        signal_period=2,
    )

    # Index 0 and 1 do not have enough data for %K.
    assert result[0] == {
        "k": None,
        "d": None,
    }

    assert result[1] == {
        "k": None,
        "d": None,
    }

    # Index 2:
    # Highest high = 14
    # Lowest low = 0
    # Close = 12
    #
    # K = (12 - 0) / (14 - 0) * 100
    #   = 85.714285...
    assert result[2]["k"] == pytest.approx(
        85.7142857143
    )

    # Only one valid K value exists,
    # so D is not available yet.
    assert result[2]["d"] is None

    # Index 3:
    # Window highs = [12, 14, 16]
    # Window lows = [2, 4, 6]
    # Close = 14
    #
    # K = (14 - 2) / (16 - 2) * 100
    #   = 85.714285...
    assert result[3]["k"] == pytest.approx(
        85.7142857143
    )

    # D = average of K at indices 2 and 3
    assert result[3]["d"] == pytest.approx(
        85.7142857143
    )


def test_stochastic_period_larger_than_data():
    highs = [10, 12]
    lows = [0, 2]
    closes = [5, 10]

    result = StochasticOscillator.calculate(
        highs,
        lows,
        closes,
        period=3,
        signal_period=2,
    )

    assert result == [
        {
            "k": None,
            "d": None,
        },
        {
            "k": None,
            "d": None,
        },
    ]


def test_stochastic_zero_price_range():
    highs = [10, 10, 10]
    lows = [10, 10, 10]
    closes = [10, 10, 10]

    result = StochasticOscillator.calculate(
        highs,
        lows,
        closes,
        period=3,
        signal_period=2,
    )

    # highest_high == lowest_low
    # Implementation returns K = 0.0
    assert result[0]["k"] is None
    assert result[1]["k"] is None

    assert result[2]["k"] == pytest.approx(0.0)

    # Only one valid K value exists,
    # so D is still unavailable.
    assert result[2]["d"] is None


def test_stochastic_signal_period():
    highs = [10, 20, 30, 40, 50]
    lows = [0, 0, 0, 0, 0]
    closes = [5, 15, 25, 35, 45]

    result = StochasticOscillator.calculate(
        highs,
        lows,
        closes,
        period=2,
        signal_period=3,
    )

    # K values:
    # index 1 = 75
    # index 2 = 83.333...
    # index 3 = 87.5
    # index 4 = 90
    assert result[1]["k"] == pytest.approx(75.0)
    assert result[2]["k"] == pytest.approx(
        83.3333333333
    )
    assert result[3]["k"] == pytest.approx(87.5)
    assert result[4]["k"] == pytest.approx(90.0)

    # D becomes available once three valid K values
    # exist: indices 1, 2, 3.
    assert result[1]["d"] is None
    assert result[2]["d"] is None

    assert result[3]["d"] == pytest.approx(
        (75.0 + 83.3333333333 + 87.5) / 3
    )

    assert result[4]["d"] == pytest.approx(
        (83.3333333333 + 87.5 + 90.0) / 3
    )