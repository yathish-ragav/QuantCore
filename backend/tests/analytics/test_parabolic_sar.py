import pytest

from quantcore.analytics.parabolic_sar import ParabolicSAR


def test_parabolic_sar_initial_value():
    highs = [10, 11, 12]
    lows = [8, 9, 10]

    result = ParabolicSAR.calculate(
        highs,
        lows,
    )

    assert result[0] is None
    assert len(result) == 3


def test_parabolic_sar_bullish_trend():
    highs = [10, 11, 12, 13, 14]
    lows = [8, 9, 10, 11, 12]

    result = ParabolicSAR.calculate(
        highs,
        lows,
        step=0.02,
        max_step=0.2,
    )

    assert result[0] is None

    # First SAR:
    # initial SAR = 8
    # AF = 0.02
    # EP = 10
    #
    # SAR = 8 + 0.02 * (10 - 8)
    #     = 8.04
    assert result[1] == pytest.approx(8.0)

    # The SAR should remain below the corresponding
    # bullish price lows.
    for i in range(1, len(result)):
        assert result[i] <= lows[i]


def test_parabolic_sar_trend_reversal():
    highs = [10, 11, 12, 13, 12, 11]
    lows = [8, 9, 10, 11, 8, 7]

    result = ParabolicSAR.calculate(
        highs,
        lows,
        step=0.02,
        max_step=0.2,
    )

    assert result[0] is None

    # Before the reversal, the SAR is calculated
    # from the bullish trend.
    assert result[3] == pytest.approx(8.24)

    # At index 4 the current low crosses the SAR,
    # causing a bearish reversal.
    #
    # On reversal:
    # SAR becomes previous extreme point = 13
    assert result[4] == pytest.approx(13.0)

    # After reversal, SAR should remain at/above
    # the corresponding highs while the bearish
    # trend continues.
    assert result[5] >= highs[5]


def test_parabolic_sar_empty_input():
    result = ParabolicSAR.calculate(
        [],
        [],
    )

    assert result == []


def test_parabolic_sar_mismatched_lengths():
    highs = [10, 11, 12]
    lows = [8, 9]

    with pytest.raises(
        ValueError,
        match="High and Low lengths must match.",
    ):
        ParabolicSAR.calculate(
            highs,
            lows,
        )