import pytest

from quantcore.analytics.rsi import RelativeStrengthIndex


def test_rsi_basic():
    prices = [100, 102, 104, 103, 105]

    result = RelativeStrengthIndex.rsi(
        prices,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] is None

    # Changes:
    # +2, +2, -1
    #
    # Average gain = (2 + 2 + 0) / 3
    #              = 1.3333...
    #
    # Average loss = (0 + 0 + 1) / 3
    #              = 0.3333...
    #
    # RS = 4
    #
    # RSI = 100 - 100 / (1 + 4)
    #     = 80
    assert result[3] == pytest.approx(80.0)

    # Last 3 changes:
    # +2, -1, +2
    #
    # Average gain = 4 / 3
    # Average loss = 1 / 3
    # RS = 4
    # RSI = 80
    assert result[4] == pytest.approx(80.0)


def test_rsi_insufficient_data():
    prices = [100, 101, 102]

    result = RelativeStrengthIndex.rsi(
        prices,
        period=3,
    )

    assert result == [
        None,
        None,
        None,
    ]


def test_rsi_all_gains():
    prices = [100, 101, 102, 103, 104]

    result = RelativeStrengthIndex.rsi(
        prices,
        period=3,
    )

    assert result[0] is None
    assert result[1] is None
    assert result[2] is None

    # No losses → RSI = 100
    assert result[3] == pytest.approx(100.0)
    assert result[4] == pytest.approx(100.0)


def test_rsi_mixed_movements():
    prices = [100, 110, 105, 115]

    result = RelativeStrengthIndex.rsi(
        prices,
        period=2,
    )

    assert result[0] is None
    assert result[1] is None

    # Last two changes at index 2:
    # +10, -5
    #
    # Average gain = 10 / 2 = 5
    # Average loss = 5 / 2 = 2.5
    #
    # RS = 2
    # RSI = 100 - 100 / 3
    #     = 66.666...
    assert result[2] == pytest.approx(
        66.6666666667
    )

    # Last two changes at index 3:
    # -5, +10
    #
    # Average gain = 10 / 2 = 5
    # Average loss = 5 / 2 = 2.5
    # RSI = 66.666...
    assert result[3] == pytest.approx(
        66.6666666667
    )


def test_rsi_all_losses():
    prices = [100, 90, 80, 70]

    result = RelativeStrengthIndex.rsi(
        prices,
        period=2,
    )

    assert result[0] is None
    assert result[1] is None

    # Average gain = 0
    # Average loss > 0
    # RSI = 0
    assert result[2] == pytest.approx(0.0)
    assert result[3] == pytest.approx(0.0)