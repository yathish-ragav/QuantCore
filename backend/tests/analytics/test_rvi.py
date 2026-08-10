import pytest

from quantcore.analytics.rvi import RelativeVigorIndex


def test_rvi_basic():
    opens = [10, 11, 12, 13]
    highs = [12, 13, 14, 15]
    lows = [8, 9, 10, 11]
    closes = [11, 12, 13, 14]

    result = RelativeVigorIndex.calculate(
        opens,
        highs,
        lows,
        closes,
        period=2,
    )

    assert result[0] is None

    # Index 1:
    #
    # Numerators:
    # 11 - 10 = 1
    # 12 - 11 = 1
    #
    # Denominators:
    # 12 - 8 = 4
    # 13 - 9 = 4
    #
    # RVI = (1 + 1) / (4 + 4)
    #     = 2 / 8
    #     = 0.25

    assert result[1] == pytest.approx(0.25)

    # Index 2:
    # Same calculation over indices 1 and 2.
    assert result[2] == pytest.approx(0.25)

    # Index 3:
    # Same calculation over indices 2 and 3.
    assert result[3] == pytest.approx(0.25)


def test_rvi_insufficient_data():
    opens = [10, 11, 12]
    highs = [12, 13, 14]
    lows = [8, 9, 10]
    closes = [11, 12, 13]

    result = RelativeVigorIndex.calculate(
        opens,
        highs,
        lows,
        closes,
        period=4,
    )

    assert result == [
        None,
        None,
        None,
    ]


def test_rvi_zero_denominator():
    opens = [10, 10]
    highs = [10, 10]
    lows = [10, 10]
    closes = [11, 11]

    result = RelativeVigorIndex.calculate(
        opens,
        highs,
        lows,
        closes,
        period=2,
    )

    # High - Low = 0 for both candles,
    # therefore denominator_sum = 0.
    assert result[0] is None
    assert result[1] is None


def test_rvi_mismatched_input_lengths():
    opens = [10, 11, 12]
    highs = [12, 13]
    lows = [8, 9, 10]
    closes = [11, 12, 13]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        RelativeVigorIndex.calculate(
            opens,
            highs,
            lows,
            closes,
            period=2,
        )


def test_rvi_invalid_period():
    opens = [10, 11, 12]
    highs = [12, 13, 14]
    lows = [8, 9, 10]
    closes = [11, 12, 13]

    with pytest.raises(
        ValueError,
        match="Period must be greater than zero.",
    ):
        RelativeVigorIndex.calculate(
            opens,
            highs,
            lows,
            closes,
            period=0,
        )