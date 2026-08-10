import pytest

from quantcore.analytics.vortex import VortexIndicator


def test_vortex_basic():
    highs = [10, 12, 14]
    lows = [8, 9, 10]
    closes = [9, 11, 13]

    result = VortexIndicator.calculate(
        highs,
        lows,
        closes,
        period=2,
    )

    assert result[0] == {
        "vortex_plus": None,
        "vortex_minus": None,
    }

    assert result[1] == {
        "vortex_plus": None,
        "vortex_minus": None,
    }

    # At index 2:
    #
    # True ranges:
    # index 1 = 3
    # index 2 = 4
    # TR sum = 7
    #
    # Positive VM:
    # index 1 = |12 - 8| = 4
    # index 2 = |14 - 9| = 5
    # VM+ sum = 9
    #
    # Negative VM:
    # index 1 = |9 - 10| = 1
    # index 2 = |10 - 12| = 2
    # VM- sum = 3

    assert result[2]["vortex_plus"] == pytest.approx(
        9 / 7
    )

    assert result[2]["vortex_minus"] == pytest.approx(
        3 / 7
    )


def test_vortex_period_larger_than_data():
    highs = [10, 12, 14]
    lows = [8, 9, 10]
    closes = [9, 11, 13]

    result = VortexIndicator.calculate(
        highs,
        lows,
        closes,
        period=5,
    )

    assert result == [
        {
            "vortex_plus": None,
            "vortex_minus": None,
        },
        {
            "vortex_plus": None,
            "vortex_minus": None,
        },
        {
            "vortex_plus": None,
            "vortex_minus": None,
        },
    ]


def test_vortex_zero_true_range():
    highs = [10, 10, 10]
    lows = [10, 10, 10]
    closes = [10, 10, 10]

    result = VortexIndicator.calculate(
        highs,
        lows,
        closes,
        period=2,
    )

    assert result[0] == {
        "vortex_plus": None,
        "vortex_minus": None,
    }

    assert result[1] == {
        "vortex_plus": None,
        "vortex_minus": None,
    }

    # TR sum is zero, so implementation returns None.
    assert result[2] == {
        "vortex_plus": None,
        "vortex_minus": None,
    }


def test_vortex_mismatched_input_lengths():
    highs = [10, 12, 14]
    lows = [8, 9]
    closes = [9, 11, 13]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        VortexIndicator.calculate(
            highs,
            lows,
            closes,
            period=2,
        )


def test_vortex_invalid_period():
    highs = [10, 12, 14]
    lows = [8, 9, 10]
    closes = [9, 11, 13]

    with pytest.raises(
        ValueError,
        match="Period must be greater than zero.",
    ):
        VortexIndicator.calculate(
            highs,
            lows,
            closes,
            period=0,
        )