from quantcore.analytics.ema import ExponentialMovingAverage


def test_ema_basic():
    prices = [10, 20, 30, 40, 50]
    period = 3

    result = ExponentialMovingAverage.ema(prices, period)

    assert result == [
        None,
        None,
        20.0,
        30.0,
        40.0,
    ]

def test_ema_period_larger_than_data():
    prices = [10, 20, 30]
    period = 5

    result = ExponentialMovingAverage.ema(prices, period)

    assert result == [
        None,
        None,
        None,
    ]

def test_ema_period_one():
    prices = [10, 20, 30, 40]

    result = ExponentialMovingAverage.ema(prices, 1)

    assert result == [
        10.0,
        20.0,
        30.0,
        40.0,
    ]