import pytest

from quantcore.analytics.coppock import CoppockCurve


def test_coppock_basic():
    closes = [
        100,
        110,
        120,
        130,
        140,
    ]

    result = CoppockCurve.calculate(
        closes,
        roc_fast_period=1,
        roc_slow_period=1,
        wma_period=2,
    )

    assert result[0] is None

    # Index 1:
    #
    # ROC = (110 - 100) / 100 * 100
    #     = 10
    #
    # Fast ROC = 10
    # Slow ROC = 10
    # ROC sum = 20
    #
    # Index 2:
    #
    # ROC = (120 - 110) / 110 * 100
    #     = 9.090909...
    #
    # ROC sum = 18.181818...
    #
    # WMA weights = [1, 2]
    #
    # WMA =
    # (20 * 1 + 18.181818 * 2) / 3
    # = 18.787878...

    assert result[2] == pytest.approx(
        18.7878787879
    )


def test_coppock_wma_weighting():
    closes = [
        100,
        110,
        130,
        160,
    ]

    result = CoppockCurve.calculate(
        closes,
        roc_fast_period=1,
        roc_slow_period=1,
        wma_period=2,
    )

    # Index 1:
    # ROC = 10%
    # ROC sum = 20%
    #
    # Index 2:
    # ROC =
    # (130 - 110) / 110 * 100
    # = 18.181818...
    #
    # ROC sum = 36.363636...
    #
    # WMA =
    # (20 * 1 + 36.363636 * 2) / 3
    # = 30.909090...

    assert result[2] == pytest.approx(
        30.9090909091
    )


def test_coppock_insufficient_data():
    closes = [
        100,
        110,
        120,
    ]

    result = CoppockCurve.calculate(
        closes,
        roc_fast_period=2,
        roc_slow_period=3,
        wma_period=2,
    )

    # Slow ROC first becomes available at index 3,
    # but the dataset ends at index 2.

    assert result == [
        None,
        None,
        None,
    ]


def test_coppock_zero_previous_close():
    closes = [
        0,
        100,
        110,
        120,
    ]

    result = CoppockCurve.calculate(
        closes,
        roc_fast_period=1,
        roc_slow_period=1,
        wma_period=2,
    )

    # Index 1:
    # Previous close = 0.
    # Both ROC values become None.

    assert result[0] is None
    assert result[1] is None

    # Index 2:
    #
    # ROC =
    # (110 - 100) / 100 * 100
    # = 10
    #
    # ROC sum = 20
    #
    # But the WMA window [index 1, index 2]
    # contains None, so result is None.

    assert result[2] is None

    # Index 3:
    #
    # ROC =
    # (120 - 110) / 110 * 100
    # = 9.090909...
    #
    # ROC sum = 18.181818...
    #
    # WMA window:
    # [20, 18.181818...]
    #
    # WMA =
    # (20 * 1 + 18.181818 * 2) / 3
    # = 18.787878...

    assert result[3] == pytest.approx(
        18.7878787879
    )


def test_coppock_empty_input():
    result = CoppockCurve.calculate(
        [],
    )

    assert result == []


def test_coppock_invalid_period():
    closes = [
        100,
        110,
        120,
    ]

    with pytest.raises(
        ValueError,
        match="Periods must be greater than zero.",
    ):
        CoppockCurve.calculate(
            closes,
            roc_fast_period=0,
            roc_slow_period=11,
            wma_period=10,
        )