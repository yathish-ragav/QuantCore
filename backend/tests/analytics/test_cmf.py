import pytest

from quantcore.analytics.cmf import ChaikinMoneyFlow


def test_cmf_basic():
    highs = [10, 12, 14, 16]
    lows = [8, 10, 12, 14]
    closes = [9, 12, 13, 15]
    volumes = [100, 200, 300, 400]

    result = ChaikinMoneyFlow.calculate(
        highs,
        lows,
        closes,
        volumes,
        period=2,
    )

    assert result[0] is None

    # Index 1:
    #
    # Candle 0:
    # High = 10, Low = 8, Close = 9
    #
    # Multiplier =
    # ((9 - 8) - (10 - 9)) / (10 - 8)
    # = 0
    #
    # MFV = 0 * 100 = 0
    #
    # Candle 1:
    # High = 12, Low = 10, Close = 12
    #
    # Multiplier =
    # ((12 - 10) - (12 - 12)) / 2
    # = 1
    #
    # MFV = 1 * 200 = 200
    #
    # CMF = 200 / (100 + 200)
    #     = 0.666666...

    assert result[1] == pytest.approx(
        200 / 300
    )

    # Index 2:
    #
    # Candle 1 MFV = 200
    #
    # Candle 2:
    # High = 14, Low = 12, Close = 13
    #
    # Multiplier =
    # ((13 - 12) - (14 - 13)) / 2
    # = 0
    #
    # MFV = 0
    #
    # CMF = 200 / (200 + 300)
    #     = 0.4

    assert result[2] == pytest.approx(0.4)


def test_cmf_period_larger_than_data():
    highs = [10, 12, 14]
    lows = [8, 10, 12]
    closes = [9, 11, 13]
    volumes = [100, 200, 300]

    result = ChaikinMoneyFlow.calculate(
        highs,
        lows,
        closes,
        volumes,
        period=5,
    )

    assert result == [
        None,
        None,
        None,
    ]


def test_cmf_zero_price_range():
    highs = [10, 10, 12]
    lows = [10, 10, 10]
    closes = [10, 10, 11]
    volumes = [100, 200, 300]

    result = ChaikinMoneyFlow.calculate(
        highs,
        lows,
        closes,
        volumes,
        period=2,
    )

    # Zero price range produces MFV = 0.
    #
    # Index 1:
    # MFV = 0 + 0
    # CMF = 0 / 300 = 0
    assert result[0] is None
    assert result[1] == pytest.approx(0.0)

    # Index 2:
    #
    # Candle 2:
    # multiplier =
    # ((11 - 10) - (12 - 11)) / 2
    # = 0
    #
    # Therefore CMF remains 0.
    assert result[2] == pytest.approx(0.0)


def test_cmf_zero_volume():
    highs = [10, 12, 14]
    lows = [8, 10, 12]
    closes = [9, 12, 13]
    volumes = [0, 0, 100]

    result = ChaikinMoneyFlow.calculate(
        highs,
        lows,
        closes,
        volumes,
        period=2,
    )

    # Index 1:
    # Volume sum = 0
    assert result[1] is None

    # Index 2:
    # Volume sum = 100
    #
    # Candle 2 has a zero money-flow multiplier,
    # so CMF = 0.
    assert result[2] == pytest.approx(0.0)


def test_cmf_mismatched_input_lengths():
    highs = [10, 12, 14]
    lows = [8, 10]
    closes = [9, 11, 13]
    volumes = [100, 200, 300]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        ChaikinMoneyFlow.calculate(
            highs,
            lows,
            closes,
            volumes,
            period=2,
        )