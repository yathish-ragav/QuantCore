import pytest

from quantcore.analytics.pvi import PositiveVolumeIndex


def test_pvi_basic():
    closes = [
        100,
        110,
        121,
        120,
    ]

    volumes = [
        100,
        200,
        300,
        200,
    ]

    result = PositiveVolumeIndex.calculate(
        closes,
        volumes,
        base_value=1000.0,
    )

    # Initial PVI
    assert result[0] == pytest.approx(1000.0)

    # Index 1:
    #
    # Volume increased:
    # 200 > 100
    #
    # Percentage change:
    # (110 - 100) / 100 = 0.10
    #
    # PVI:
    # 1000 * (1 + 0.10)
    # = 1100

    assert result[1] == pytest.approx(1100.0)

    # Index 2:
    #
    # Volume increased:
    # 300 > 200
    #
    # Percentage change:
    # (121 - 110) / 110
    # = 0.10
    #
    # PVI:
    # 1100 * 1.10
    # = 1210

    assert result[2] == pytest.approx(1210.0)

    # Index 3:
    #
    # Volume decreased:
    # 200 < 300
    #
    # Therefore PVI does not change.

    assert result[3] == pytest.approx(1210.0)


def test_pvi_volume_decrease_does_not_change_pvi():
    closes = [
        100,
        110,
        120,
        130,
    ]

    volumes = [
        100,
        200,
        300,
        200,
    ]

    result = PositiveVolumeIndex.calculate(
        closes,
        volumes,
        base_value=1000.0,
    )

    # PVI updates at indices 1 and 2.
    assert result[1] == pytest.approx(1100.0)
    assert result[2] == pytest.approx(1200.0)

    # Volume decreases at index 3,
    # so PVI remains unchanged.

    assert result[3] == pytest.approx(1200.0)


def test_pvi_equal_volume_does_not_change_pvi():
    closes = [
        100,
        110,
        120,
    ]

    volumes = [
        100,
        200,
        200,
    ]

    result = PositiveVolumeIndex.calculate(
        closes,
        volumes,
        base_value=1000.0,
    )

    # Index 1:
    # Volume increased -> update.

    assert result[1] == pytest.approx(1100.0)

    # Index 2:
    # Volume stayed the same.
    #
    # Condition is:
    # volumes[i] > volumes[i - 1]
    #
    # Therefore PVI does not change.

    assert result[2] == pytest.approx(1100.0)


def test_pvi_zero_previous_close():
    closes = [
        0,
        100,
        110,
    ]

    volumes = [
        100,
        200,
        300,
    ]

    result = PositiveVolumeIndex.calculate(
        closes,
        volumes,
        base_value=1000.0,
    )

    # Index 1:
    #
    # Previous close = 0.
    #
    # The implementation explicitly keeps
    # the current PVI unchanged.

    assert result[0] == pytest.approx(1000.0)
    assert result[1] == pytest.approx(1000.0)

    # Index 2:
    #
    # Previous close = 100.
    # Volume increased.
    #
    # Percentage change = 10 / 100 = 0.10
    #
    # PVI = 1000 * 1.10 = 1100

    assert result[2] == pytest.approx(1100.0)


def test_pvi_custom_base_value():
    closes = [
        100,
        110,
    ]

    volumes = [
        100,
        200,
    ]

    result = PositiveVolumeIndex.calculate(
        closes,
        volumes,
        base_value=500.0,
    )

    assert result[0] == pytest.approx(500.0)

    # Volume increased:
    # 200 > 100
    #
    # PVI = 500 * 1.10 = 550

    assert result[1] == pytest.approx(550.0)


def test_pvi_empty_input():
    result = PositiveVolumeIndex.calculate(
        [],
        [],
    )

    assert result == []


def test_pvi_mismatched_input_lengths():
    closes = [
        100,
        110,
        120,
    ]

    volumes = [
        100,
        200,
    ]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        PositiveVolumeIndex.calculate(
            closes,
            volumes,
        )