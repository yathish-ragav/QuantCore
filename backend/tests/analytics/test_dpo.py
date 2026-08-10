import pytest

from quantcore.analytics.dpo import DetrendedPriceOscillator


def test_dpo_basic():
    closes = [
        10,
        12,
        14,
        16,
        18,
        20,
        30,
    ]

    result = DetrendedPriceOscillator.calculate(
        closes,
        period=4,
    )

    # Period = 4
    # Displacement = (4 // 2) + 1 = 3
    #
    # First valid index:
    # period - 1 + displacement
    # = 3 + 3
    # = 6

    for i in range(6):
        assert result[i] is None

    # At index 6:
    #
    # SMA window = closes[3:7]
    #            = [16, 18, 20, 30]
    #
    # SMA = 84 / 4 = 21
    #
    # Displaced close:
    # closes[6 - 3] = closes[3] = 16
    #
    # DPO = 16 - 21 = -5

    assert result[6] == pytest.approx(-5.0)


def test_dpo_multiple_values():
    closes = [
        10,
        12,
        14,
        16,
        18,
        20,
        30,
        32,
    ]

    result = DetrendedPriceOscillator.calculate(
        closes,
        period=4,
    )

    # Index 6:
    # SMA = (16 + 18 + 20 + 30) / 4 = 21
    # Displaced close = 16
    # DPO = -5

    assert result[6] == pytest.approx(-5.0)

    # Index 7:
    # SMA = (18 + 20 + 30 + 32) / 4 = 25
    # Displaced close = 18
    # DPO = -7

    assert result[7] == pytest.approx(-7.0)


def test_dpo_insufficient_data():
    closes = [
        10,
        12,
        14,
        16,
        18,
        20,
    ]

    result = DetrendedPriceOscillator.calculate(
        closes,
        period=4,
    )

    # First valid index would be 6,
    # but the final index is only 5.

    assert result == [
        None,
        None,
        None,
        None,
        None,
        None,
    ]


def test_dpo_invalid_period():
    closes = [10, 12, 14, 16]

    with pytest.raises(
        ValueError,
        match="Period must be greater than zero.",
    ):
        DetrendedPriceOscillator.calculate(
            closes,
            period=0,
        )