import pytest
from quantcore.analytics.accumulation_distribution import AccumulationDistribution


def test_ad_basic():
    highs = [10, 12]
    lows = [8, 8]
    closes = [10, 9]
    volumes = [100, 200]

    result = AccumulationDistribution.ad(
        highs,
        lows,
        closes,
        volumes,
    )

    assert result == [
        100.0,
        0.0,
    ]

def test_ad_zero_price_range():
    highs = [10]
    lows = [10]
    closes = [10]
    volumes = [100]

    result = AccumulationDistribution.ad(
        highs,
        lows,
        closes,
        volumes,
    )

    assert result == [0.0]

def test_ad_mismatched_input_lengths():
    highs = [10, 12]
    lows = [8]
    closes = [10, 9]
    volumes = [100, 200]

    with pytest.raises(ValueError, match="Input lengths must match."):
        AccumulationDistribution.ad(
            highs,
            lows,
            closes,
            volumes,
        )