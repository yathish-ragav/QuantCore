import pytest

from quantcore.analytics.mfi import MoneyFlowIndex


def test_mfi_basic():
    highs = [11, 13, 15, 14]
    lows = [9, 11, 13, 12]
    closes = [10, 12, 14, 13]
    volumes = [100, 100, 100, 100]

    result = MoneyFlowIndex.calculate(
        highs,
        lows,
        closes,
        volumes,
        period=3,
    )

    # Typical prices:
    # 10, 12, 14, 13
    #
    # At index 2:
    # positive flow = 12*100 + 14*100
    # negative flow = 0
    # Therefore MFI = 100
    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(100.0)

    # At index 3:
    # Positive flow = 12*100 + 14*100 = 2600
    # Negative flow = 13*100 = 1300
    #
    # Money ratio = 2600 / 1300 = 2
    # MFI = 100 - 100/(1+2)
    #     = 66.666...
    assert result[3] == pytest.approx(66.6666666667)


def test_mfi_period_larger_than_data():
    highs = [11, 13]
    lows = [9, 11]
    closes = [10, 12]
    volumes = [100, 100]

    result = MoneyFlowIndex.calculate(
        highs,
        lows,
        closes,
        volumes,
        period=3,
    )

    assert result == [
        None,
        None,
    ]


def test_mfi_no_negative_flow():
    highs = [11, 13, 15]
    lows = [9, 11, 13]
    closes = [10, 12, 14]
    volumes = [100, 100, 100]

    result = MoneyFlowIndex.calculate(
        highs,
        lows,
        closes,
        volumes,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(100.0)


def test_mfi_mismatched_input_lengths():
    highs = [11, 13, 15]
    lows = [9, 11]
    closes = [10, 12, 14]
    volumes = [100, 100, 100]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        MoneyFlowIndex.calculate(
            highs,
            lows,
            closes,
            volumes,
            period=3,
        )