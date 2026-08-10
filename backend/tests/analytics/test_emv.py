import pytest

from quantcore.analytics.emv import EaseOfMovement


def test_emv_basic():
    highs = [10, 12, 14, 16]
    lows = [8, 10, 12, 14]
    volumes = [100, 100, 100, 100]

    result = EaseOfMovement.emv(
        highs,
        lows,
        volumes,
        period=2,
    )

    # Midpoints: 9, 11, 13, 15
    # Midpoint move: 2
    # Price range: 2
    # Box ratio: 100 / 2 = 50
    # Raw EMV: 2 / 50 = 0.04
    #
    # At index 2:
    # average of raw EMV at indices 1 and 2 = 0.04

    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(0.04)
    assert result[3] == pytest.approx(0.04)


def test_emv_period_larger_than_data():
    highs = [10, 12, 14]
    lows = [8, 10, 12]
    volumes = [100, 100, 100]

    result = EaseOfMovement.emv(
        highs,
        lows,
        volumes,
        period=5,
    )

    assert result == [
        None,
        None,
        None,
    ]


def test_emv_zero_price_range():
    highs = [10, 10, 12]
    lows = [8, 10, 10]
    volumes = [100, 100, 100]

    result = EaseOfMovement.emv(
        highs,
        lows,
        volumes,
        period=1,
    )

    assert result[0] is None
    assert result[1] is None

    # At index 2:
    # midpoint[1] = 10
    # midpoint[2] = 11
    # midpoint move = 1
    # price range = 2
    # box ratio = 100 / 2 = 50
    # EMV = 1 / 50 = 0.02
    assert result[2] == pytest.approx(0.02)


def test_emv_zero_volume():
    highs = [10, 12, 14]
    lows = [8, 10, 12]
    volumes = [100, 0, 100]

    result = EaseOfMovement.emv(
        highs,
        lows,
        volumes,
        period=1,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(0.04)


def test_emv_mismatched_input_lengths():
    highs = [10, 12, 14]
    lows = [8, 10]
    volumes = [100, 100, 100]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        EaseOfMovement.emv(
            highs,
            lows,
            volumes,
            period=2,
        )


def test_emv_invalid_period():
    highs = [10, 12, 14]
    lows = [8, 10, 12]
    volumes = [100, 100, 100]

    with pytest.raises(
        ValueError,
        match="Period must be greater than zero.",
    ):
        EaseOfMovement.emv(
            highs,
            lows,
            volumes,
            period=0,
        )