import pytest

from quantcore.analytics.roc import RateOfChange


def test_roc_basic():
    closes = [100, 110, 120, 90]

    result = RateOfChange.calculate(
        closes,
        period=2,
    )

    # First two values are unavailable.
    assert result[0] is None
    assert result[1] is None

    # (120 - 100) / 100 * 100 = 20%
    assert result[2] == pytest.approx(20.0)

    # (90 - 110) / 110 * 100 = -18.1818...
    assert result[3] == pytest.approx(
        -18.1818181818
    )


def test_roc_period_larger_than_data():
    closes = [100, 110, 120]

    result = RateOfChange.calculate(
        closes,
        period=5,
    )

    assert result == [
        None,
        None,
        None,
    ]


def test_roc_zero_previous_close():
    closes = [0, 100, 50]

    result = RateOfChange.calculate(
        closes,
        period=1,
    )

    # At index 1, previous close is 0,
    # so implementation returns 0.0.
    assert result[0] is None
    assert result[1] == pytest.approx(0.0)

    # At index 2:
    # (50 - 100) / 100 * 100 = -50%
    assert result[2] == pytest.approx(-50.0)


def test_roc_unchanged_price():
    closes = [100, 100, 100, 100]

    result = RateOfChange.calculate(
        closes,
        period=2,
    )

    assert result == [
        None,
        None,
        0.0,
        0.0,
    ]