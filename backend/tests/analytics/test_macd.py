import pytest

from quantcore.analytics.macd import MACD


def test_macd_basic():
    prices = [
        10, 11, 12, 13, 14,
        15, 16, 17, 18, 19,
    ]

    result = MACD.macd(
        prices,
        fast_period=3,
        slow_period=5,
        signal_period=2,
    )

    # MACD becomes available once the slow EMA
    # becomes available (index 4).
    assert result[0] == {
        "macd": None,
        "signal": None,
        "histogram": None,
    }

    assert result[3] == {
        "macd": None,
        "signal": None,
        "histogram": None,
    }

    # Fast EMA at index 4:
    # initial fast EMA = (10 + 11 + 12) / 3 = 11
    # next = (13 - 11) * 0.5 + 11 = 12
    # next = (14 - 12) * 0.5 + 12 = 13
    #
    # Slow EMA at index 4:
    # (10 + 11 + 12 + 13 + 14) / 5 = 12
    #
    # MACD = 13 - 12 = 1
    assert result[4]["macd"] == pytest.approx(1.0)

    # There is only one valid MACD value at this point,
    # so a signal EMA with period 2 cannot exist yet.
    assert result[4]["signal"] is None
    assert result[4]["histogram"] is None

    # At index 5:
    # Fast EMA = (15 - 13) * 0.5 + 13 = 14
    # Slow EMA = (15 - 12) * 0.333333... + 12 = 13
    # MACD = 1
    assert result[5]["macd"] == pytest.approx(1.0)

    # Signal EMA from [1, 1] with period 2 = 1
    assert result[5]["signal"] == pytest.approx(1.0)
    assert result[5]["histogram"] == pytest.approx(0.0)


def test_macd_insufficient_data():
    prices = [10, 11, 12, 13]

    result = MACD.macd(
        prices,
        fast_period=3,
        slow_period=5,
        signal_period=2,
    )

    assert result == [
        {
            "macd": None,
            "signal": None,
            "histogram": None,
        },
        {
            "macd": None,
            "signal": None,
            "histogram": None,
        },
        {
            "macd": None,
            "signal": None,
            "histogram": None,
        },
        {
            "macd": None,
            "signal": None,
            "histogram": None,
        },
    ]


def test_macd_histogram_equals_macd_minus_signal():
    prices = [
        10, 11, 12, 13, 14,
        15, 16, 17, 18, 19,
    ]

    result = MACD.macd(
        prices,
        fast_period=3,
        slow_period=5,
        signal_period=2,
    )

    for value in result:
        if (
            value["macd"] is not None
            and value["signal"] is not None
        ):
            assert value["histogram"] == pytest.approx(
                value["macd"] - value["signal"]
            )