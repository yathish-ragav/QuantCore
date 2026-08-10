import pytest

from quantcore.analytics.ichimoku import IchimokuCloud


def test_ichimoku_basic():
    highs = list(range(1, 53))
    lows = list(range(0, 52))

    result = IchimokuCloud.calculate(
        highs,
        lows,
    )

    # Before 9 periods, nothing is available.
    assert result[0] == {
        "tenkan": None,
        "kijun": None,
        "span_a": None,
        "span_b": None,
    }

    assert result[7] == {
        "tenkan": None,
        "kijun": None,
        "span_a": None,
        "span_b": None,
    }

    # At index 8:
    # Highs 1..9 -> highest = 9
    # Lows 0..8  -> lowest = 0
    # Tenkan = (9 + 0) / 2 = 4.5
    assert result[8]["tenkan"] == pytest.approx(4.5)
    assert result[8]["kijun"] is None
    assert result[8]["span_a"] is None
    assert result[8]["span_b"] is None

    # At index 25:
    # Tenkan window: highs 18..26, lows 17..25
    # Tenkan = (26 + 17) / 2 = 21.5
    #
    # Kijun window: highs 1..26, lows 0..25
    # Kijun = (26 + 0) / 2 = 13
    #
    # Span A = (21.5 + 13) / 2 = 17.25
    assert result[25]["tenkan"] == pytest.approx(21.5)
    assert result[25]["kijun"] == pytest.approx(13.0)
    assert result[25]["span_a"] == pytest.approx(17.25)
    assert result[25]["span_b"] is None

    # At index 51:
    # Tenkan = (52 + 43) / 2 = 47.5
    # Kijun = (52 + 26) / 2 = 39
    # Span A = (47.5 + 39) / 2 = 43.25
    #
    # Span B uses the full 52-period window:
    # highest = 52
    # lowest = 0
    # Span B = 26
    assert result[51]["tenkan"] == pytest.approx(47.5)
    assert result[51]["kijun"] == pytest.approx(39.0)
    assert result[51]["span_a"] == pytest.approx(43.25)
    assert result[51]["span_b"] == pytest.approx(26.0)


def test_ichimoku_insufficient_data():
    highs = list(range(1, 20))
    lows = list(range(0, 19))

    result = IchimokuCloud.calculate(
        highs,
        lows,
    )

    # 19 values are not enough for Kijun or Span B.
    assert result[-1]["tenkan"] is not None
    assert result[-1]["kijun"] is None
    assert result[-1]["span_a"] is None
    assert result[-1]["span_b"] is None


def test_ichimoku_mismatched_input_lengths():
    highs = [10, 11, 12]
    lows = [8, 9]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        IchimokuCloud.calculate(
            highs,
            lows,
        )