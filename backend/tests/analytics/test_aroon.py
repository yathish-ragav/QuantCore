import pytest

from quantcore.analytics.aroon import Aroon


def test_aroon_basic():
    highs = [10, 12, 11, 13]
    lows = [8, 9, 7, 10]

    result = Aroon.calculate(
        highs,
        lows,
        period=3,
    )

    assert result[0] == {
        "aroon_up": None,
        "aroon_down": None,
    }

    assert result[1] == {
        "aroon_up": None,
        "aroon_down": None,
    }

    assert result[2]["aroon_up"] == pytest.approx(66.6666666667)
    assert result[2]["aroon_down"] == pytest.approx(100.0)

    assert result[3]["aroon_up"] == pytest.approx(100.0)
    assert result[3]["aroon_down"] == pytest.approx(66.6666666667)


def test_aroon_period_larger_than_data():
    highs = [10, 12, 11]
    lows = [8, 9, 7]

    result = Aroon.calculate(
        highs,
        lows,
        period=5,
    )

    assert result == [
        {
            "aroon_up": None,
            "aroon_down": None,
        },
        {
            "aroon_up": None,
            "aroon_down": None,
        },
        {
            "aroon_up": None,
            "aroon_down": None,
        },
    ]


def test_aroon_mismatched_input_lengths():
    highs = [10, 12, 11]
    lows = [8, 9]

    with pytest.raises(
        ValueError,
        match="Input lengths must match.",
    ):
        Aroon.calculate(
            highs,
            lows,
            period=3,
        )