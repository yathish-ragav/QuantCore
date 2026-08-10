import pytest

from quantcore.analytics.trix import TRIX


def test_trix_basic():
    closes = [
        100,
        110,
        120,
        130,
    ]

    result = TRIX.calculate(
        closes,
        period=2,
    )

    assert result[0] is None

    # Triple EMA with period 2:
    #
    # EMA1:
    # 100
    # 106.666666...
    # 115.555555...
    # 125.185185...
    #
    # EMA2:
    # 100
    # 104.444444...
    # 111.851851...
    # 120.740740...
    #
    # EMA3:
    # 100
    # 102.962962...
    # 108.888888...
    # 116.296296...
    #
    # TRIX[1]:
    #
    # ((102.962962 - 100) / 100) * 100
    # = 2.962962...

    assert result[1] == pytest.approx(
        2.9629629629
    )


def test_trix_multiple_values():
    closes = [
        100,
        110,
        120,
        130,
        140,
    ]

    result = TRIX.calculate(
        closes,
        period=2,
    )

    assert result[0] is None

    # The triple EMA continues increasing,
    # so TRIX remains positive.

    assert result[1] > 0
    assert result[2] > 0
    assert result[3] > 0
    assert result[4] > 0

    # For this particular steadily increasing
    # sequence, the TRIX values increase.

    assert result[2] > result[1]
    assert result[3] > result[2]
    assert result[4] > result[3]


def test_trix_constant_prices():
    closes = [
        100,
        100,
        100,
        100,
        100,
    ]

    result = TRIX.calculate(
        closes,
        period=3,
    )

    assert result[0] is None

    for value in result[1:]:
        assert value == pytest.approx(0.0)


def test_trix_zero_previous_ema():
    closes = [
        0,
        0,
        10,
        20,
    ]

    result = TRIX.calculate(
        closes,
        period=2,
    )

    # EMA3[0] = 0.
    #
    # At index 1:
    # previous EMA3 = 0
    #
    # The implementation explicitly returns 0.0.

    assert result[0] is None
    assert result[1] == pytest.approx(0.0)

    # Once EMA3 becomes positive, normal TRIX
    # calculation resumes.

    assert result[2] is not None
    assert result[3] is not None


def test_trix_empty_input():
    result = TRIX.calculate(
        [],
        period=15,
    )

    # The implementation initializes:
    #
    # result = [None]
    #
    # even when closes is empty.

    assert result == [None]