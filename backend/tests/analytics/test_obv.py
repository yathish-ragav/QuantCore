import pytest

from quantcore.analytics.obv import OnBalanceVolume


def test_obv_basic():
    closes = [100, 105, 102, 110]
    volumes = [1000, 2000, 3000, 4000]

    result = OnBalanceVolume.calculate(
        closes,
        volumes,
    )

    # Initial OBV
    assert result[0] == 0

    # Price increased: +2000
    assert result[1] == 2000

    # Price decreased: -3000
    assert result[2] == -1000

    # Price increased: +4000
    assert result[3] == 3000


def test_obv_unchanged_price():
    closes = [100, 100, 100]
    volumes = [1000, 2000, 3000]

    result = OnBalanceVolume.calculate(
        closes,
        volumes,
    )

    assert result == [
        0,
        0,
        0,
    ]


def test_obv_mixed_price_movements():
    closes = [100, 105, 105, 95, 100]
    volumes = [1000, 2000, 3000, 4000, 5000]

    result = OnBalanceVolume.calculate(
        closes,
        volumes,
    )

    assert result == [
        0,
        2000,
        2000,
        -2000,
        3000,
    ]


def test_obv_mismatched_input_lengths():
    closes = [100, 105, 110]
    volumes = [1000, 2000]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        OnBalanceVolume.calculate(
            closes,
            volumes,
        )


def test_obv_empty_input():
    result = OnBalanceVolume.calculate(
        [],
        [],
    )

    assert result == []