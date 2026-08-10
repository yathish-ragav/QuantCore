import pytest

from quantcore.analytics.vwap import VolumeWeightedAveragePrice


def test_vwap_basic():
    highs = [11, 13, 15]
    lows = [9, 11, 13]
    closes = [10, 12, 14]
    volumes = [100, 200, 300]

    result = VolumeWeightedAveragePrice.calculate(
        highs,
        lows,
        closes,
        volumes,
    )

    # Typical prices:
    # 10, 12, 14
    #
    # Cumulative VWAP:
    #
    # Index 0:
    # (10 * 100) / 100 = 10
    #
    # Index 1:
    # (10*100 + 12*200) / 300
    # = 3400 / 300
    # = 11.3333...
    #
    # Index 2:
    # (10*100 + 12*200 + 14*300) / 600
    # = 7600 / 600
    # = 12.6666...

    assert result[0] == pytest.approx(10.0)
    assert result[1] == pytest.approx(11.3333333333)
    assert result[2] == pytest.approx(12.6666666667)


def test_vwap_zero_volume():
    highs = [10, 12]
    lows = [10, 12]
    closes = [10, 12]
    volumes = [0, 100]

    result = VolumeWeightedAveragePrice.calculate(
        highs,
        lows,
        closes,
        volumes,
    )

    # First candle has zero cumulative volume.
    assert result[0] is None

    # Second candle:
    # Typical price = 12
    # Cumulative volume = 100
    assert result[1] == pytest.approx(12.0)


def test_vwap_multiple_zero_volume_periods():
    highs = [10, 12, 14]
    lows = [10, 12, 14]
    closes = [10, 12, 14]
    volumes = [0, 0, 100]

    result = VolumeWeightedAveragePrice.calculate(
        highs,
        lows,
        closes,
        volumes,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(14.0)


def test_vwap_mismatched_input_lengths():
    highs = [11, 13, 15]
    lows = [9, 11]
    closes = [10, 12, 14]
    volumes = [100, 200, 300]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        VolumeWeightedAveragePrice.calculate(
            highs,
            lows,
            closes,
            volumes,
        )