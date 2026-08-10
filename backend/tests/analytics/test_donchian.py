import pytest

from quantcore.analytics.donchian import DonchianChannels


def test_donchian_basic():
    highs = [10, 15, 12, 20]
    lows = [5, 8, 6, 10]

    result = DonchianChannels.calculate(
        highs,
        lows,
        period=3,
    )

    assert result[0] == {
        "upper": None,
        "middle": None,
        "lower": None,
    }

    assert result[1] == {
        "upper": None,
        "middle": None,
        "lower": None,
    }

    # Window = highs [10, 15, 12], lows [5, 8, 6]
    # Upper = 15
    # Lower = 5
    # Middle = 10
    assert result[2] == {
        "upper": 15,
        "middle": 10.0,
        "lower": 5,
    }

    # Window = highs [15, 12, 20], lows [8, 6, 10]
    # Upper = 20
    # Lower = 6
    # Middle = 13
    assert result[3] == {
        "upper": 20,
        "middle": 13.0,
        "lower": 6,
    }


def test_donchian_period_larger_than_data():
    highs = [10, 15]
    lows = [5, 8]

    result = DonchianChannels.calculate(
        highs,
        lows,
        period=3,
    )

    assert result == [
        {
            "upper": None,
            "middle": None,
            "lower": None,
        },
        {
            "upper": None,
            "middle": None,
            "lower": None,
        },
    ]


def test_donchian_mismatched_input_lengths():
    highs = [10, 15, 12]
    lows = [5, 8]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        DonchianChannels.calculate(
            highs,
            lows,
            period=3,
        )