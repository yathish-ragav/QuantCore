from quantcore.analytics.moving_average import MovingAverage


def test_sma_basic():
    prices = [10, 20, 30, 40, 50]
    period = 3

    result = MovingAverage.sma(prices, period)

    assert result == [
        None,
        None,
        20.0,
        30.0,
        40.0,
    ]

def test_sma_period_larger_than_data():
    prices = [10, 20, 30]
    period = 5

    result = MovingAverage.sma(prices, period)

    assert result == [
        None,
        None,
        None,
    ]

def test_sma_period_one():
    prices = [10, 20, 30, 40]

    result = MovingAverage.sma(prices, 1)

    assert result == [
        10.0,
        20.0,
        30.0,
        40.0,
    ]