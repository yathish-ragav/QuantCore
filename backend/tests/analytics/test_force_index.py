import pytest

from quantcore.analytics.force_index import ForceIndex


def test_force_index_basic():
    closes = [100, 105, 103, 110]
    volumes = [1000, 2000, 3000, 4000]

    result = ForceIndex.force_index(
        closes,
        volumes,
    )

    assert result[0] is None

    # (105 - 100) * 2000 = 10000
    assert result[1] == pytest.approx(10000.0)

    # (103 - 105) * 3000 = -6000
    assert result[2] == pytest.approx(-6000.0)

    # (110 - 103) * 4000 = 28000
    assert result[3] == pytest.approx(28000.0)


def test_force_index_unchanged_price():
    closes = [100, 100, 100]
    volumes = [1000, 2000, 3000]

    result = ForceIndex.force_index(
        closes,
        volumes,
    )

    assert result == [
        None,
        0.0,
        0.0,
    ]


def test_force_index_volume_effect():
    closes = [100, 105, 110]
    volumes = [1000, 2000, 4000]

    result = ForceIndex.force_index(
        closes,
        volumes,
    )

    # Same price movement of +5,
    # but different volumes.
    assert result[0] is None
    assert result[1] == pytest.approx(10000.0)
    assert result[2] == pytest.approx(20000.0)