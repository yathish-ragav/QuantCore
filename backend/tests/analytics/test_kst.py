import pytest

from quantcore.analytics.kst import KnowSureThing


def test_kst_basic():
    closes = [
        100,
        110,
        120,
        130,
        140,
    ]

    result = KnowSureThing.calculate(
        closes,
        roc1_period=1,
        roc2_period=1,
        roc3_period=1,
        roc4_period=1,
        sma1_period=1,
        sma2_period=1,
        sma3_period=1,
        sma4_period=1,
    )

    assert result[0] is None

    # At index 1:
    # ROC = (110 - 100) / 100 * 100 = 10
    #
    # All four ROC values = 10
    # All four SMA values = 10
    #
    # KST =
    # 10 + 2(10) + 3(10) + 4(10)
    # = 100

    assert result[1] == pytest.approx(100.0)

    # Index 2:
    # ROC = (120 - 110) / 110 * 100
    #     = 9.090909...
    #
    # KST = 10 * ROC
    assert result[2] == pytest.approx(
        90.9090909091
    )

    assert result[3] == pytest.approx(
        (10 / 120 * 100) * 10
    )


def test_kst_default_period_warmup():
    closes = list(range(100, 151))

    result = KnowSureThing.calculate(closes)

    # The slowest component is:
    # ROC4 period = 30
    # SMA4 period = 15
    #
    # First ROC4 value appears at index 30.
    # The first 15-value SMA window containing
    # valid ROC4 values therefore ends at:
    #
    # 30 + 15 - 1 = 44
    #
    # Therefore KST should first become available
    # at index 44.

    for i in range(44):
        assert result[i] is None

    assert result[44] is not None


def test_kst_zero_previous_close():
    closes = [
        0,
        100,
        110,
    ]

    result = KnowSureThing.calculate(
        closes,
        roc1_period=1,
        roc2_period=1,
        roc3_period=1,
        roc4_period=1,
        sma1_period=1,
        sma2_period=1,
        sma3_period=1,
        sma4_period=1,
    )

    # At index 1, previous close is zero.
    # All ROC calculations return None.
    assert result[0] is None
    assert result[1] is None

    # At index 2:
    # ROC = (110 - 100) / 100 * 100 = 10
    #
    # All four SMAs = 10
    # KST = 10 + 20 + 30 + 40 = 100
    assert result[2] == pytest.approx(100.0)


def test_kst_weighted_components():
    closes = [
        100,
        110,
        121,
    ]

    result = KnowSureThing.calculate(
        closes,
        roc1_period=1,
        roc2_period=1,
        roc3_period=1,
        roc4_period=1,
        sma1_period=1,
        sma2_period=1,
        sma3_period=1,
        sma4_period=1,
    )

    # Index 1:
    # ROC = 10%
    # KST = 10 + 20 + 30 + 40 = 100
    assert result[1] == pytest.approx(100.0)

    # Index 2:
    # ROC = (121 - 110) / 110 * 100 = 10%
    # KST remains 100.
    assert result[2] == pytest.approx(100.0)