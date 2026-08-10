import pytest

from quantcore.analytics.elder_ray import ElderRayIndex


def test_elder_ray_basic():
    highs = [11, 13, 15, 18]
    lows = [9, 10, 11, 12]
    closes = [10, 12, 14, 16]

    result = ElderRayIndex.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    # First two values are in the EMA warm-up period.
    assert result[0] == {
        "bull_power": None,
        "bear_power": None,
    }

    assert result[1] == {
        "bull_power": None,
        "bear_power": None,
    }

    # Initial EMA = (10 + 12 + 14) / 3 = 12
    assert result[2]["bull_power"] == pytest.approx(15 - 12)
    assert result[2]["bear_power"] == pytest.approx(11 - 12)

    # Next EMA:
    # EMA = (16 - 12) * 0.5 + 12 = 14
    assert result[3]["bull_power"] == pytest.approx(18 - 14)
    assert result[3]["bear_power"] == pytest.approx(12 - 14)


def test_elder_ray_period_larger_than_data():
    highs = [11, 13]
    lows = [9, 10]
    closes = [10, 12]

    result = ElderRayIndex.calculate(
        highs,
        lows,
        closes,
        period=3,
    )

    assert result == [
        {
            "bull_power": None,
            "bear_power": None,
        },
        {
            "bull_power": None,
            "bear_power": None,
        },
    ]


def test_elder_ray_mismatched_input_lengths():
    highs = [11, 13, 15]
    lows = [9, 10]
    closes = [10, 12, 14]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        ElderRayIndex.calculate(
            highs,
            lows,
            closes,
            period=3,
        )


def test_elder_ray_invalid_period():
    highs = [11, 13, 15]
    lows = [9, 10, 11]
    closes = [10, 12, 14]

    with pytest.raises(
        ValueError,
        match="Period must be greater than zero.",
    ):
        ElderRayIndex.calculate(
            highs,
            lows,
            closes,
            period=0,
        )