import pytest

from quantcore.analytics.bollinger import BollingerBands


def test_bollinger_basic():
    prices = [10, 20, 30, 40]

    result = BollingerBands.calculate(
        prices,
        period=3,
        multiplier=2.0,
    )

    assert result[0] == {
        "middle": None,
        "upper": None,
        "lower": None,
    }

    assert result[1] == {
        "middle": None,
        "upper": None,
        "lower": None,
    }

    # Window = [10, 20, 30]
    # SMA = 20
    std = (200 / 3) ** 0.5

    assert result[2]["middle"] == 20.0
    assert result[2]["upper"] == pytest.approx(20 + 2 * std)
    assert result[2]["lower"] == pytest.approx(20 - 2 * std)

    # Window = [20, 30, 40]
    # SMA = 30
    # Same standard deviation
    assert result[3]["middle"] == 30.0
    assert result[3]["upper"] == pytest.approx(30 + 2 * std)
    assert result[3]["lower"] == pytest.approx(30 - 2 * std)


def test_bollinger_period_larger_than_data():
    prices = [10, 20, 30]

    result = BollingerBands.calculate(
        prices,
        period=5,
    )

    assert result == [
        {
            "middle": None,
            "upper": None,
            "lower": None,
        },
        {
            "middle": None,
            "upper": None,
            "lower": None,
        },
        {
            "middle": None,
            "upper": None,
            "lower": None,
        },
    ]


def test_bollinger_constant_prices():
    prices = [50, 50, 50]

    result = BollingerBands.calculate(
        prices,
        period=3,
    )

    assert result[0]["middle"] is None
    assert result[1]["middle"] is None

    assert result[2]["middle"] == 50.0
    assert result[2]["upper"] == 50.0
    assert result[2]["lower"] == 50.0