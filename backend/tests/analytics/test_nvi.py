import pytest

from quantcore.analytics.nvi import NegativeVolumeIndex


def test_nvi_basic():
    closes = [100, 105, 110, 108]
    volumes = [1000, 900, 1000, 800]

    result = NegativeVolumeIndex.calculate(
        closes,
        volumes,
        base_value=1000.0,
    )

    assert result[0] == pytest.approx(1000.0)

    # Volume decreased: 1000 -> 900
    # Close increased by 5%
    # NVI = 1000 * 1.05 = 1050
    assert result[1] == pytest.approx(1050.0)

    # Volume increased: 900 -> 1000
    # NVI remains unchanged
    assert result[2] == pytest.approx(1050.0)

    # Volume decreased: 1000 -> 800
    # Close change = (108 - 110) / 110
    # NVI = 1050 * (108 / 110)
    assert result[3] == pytest.approx(
        1050 * (108 / 110)
    )


def test_nvi_volume_increase_keeps_value_unchanged():
    closes = [100, 110, 120]
    volumes = [1000, 1100, 1200]

    result = NegativeVolumeIndex.calculate(
        closes,
        volumes,
    )

    assert result == [
        1000.0,
        1000.0,
        1000.0,
    ]


def test_nvi_zero_previous_close():
    closes = [0, 100, 110]
    volumes = [1000, 900, 800]

    result = NegativeVolumeIndex.calculate(
        closes,
        volumes,
    )

    assert result == [
        1000.0,
        1000.0,
        1100.0,
    ]


def test_nvi_custom_base_value():
    closes = [100, 110]
    volumes = [1000, 900]

    result = NegativeVolumeIndex.calculate(
        closes,
        volumes,
        base_value=5000.0,
    )

    assert result == [
        5000.0,
        5500.0,
    ]


def test_nvi_mismatched_input_lengths():
    closes = [100, 105, 110]
    volumes = [1000, 900]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        NegativeVolumeIndex.calculate(
            closes,
            volumes,
        )


def test_nvi_empty_input():
    result = NegativeVolumeIndex.calculate(
        [],
        [],
    )

    assert result == []