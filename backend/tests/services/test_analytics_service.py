from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quantcore.services.analytics_service import AnalyticsService


def make_price(
    date,
    open_price=100.0,
    high=105.0,
    low=95.0,
    close=102.0,
    volume=1_000_000,
):
    return SimpleNamespace(
        date=date,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def make_service():

    db = Mock()

    service = AnalyticsService.__new__(
        AnalyticsService
    )

    service.company_repo = Mock()
    service.price_repo = Mock()

    return service, db


def make_prices():

    return [
        make_price(
            datetime(2026, 1, 1),
            100.0,
            105.0,
            95.0,
            102.0,
            1_000_000,
        ),
        make_price(
            datetime(2026, 1, 2),
            102.0,
            108.0,
            99.0,
            106.0,
            1_200_000,
        ),
    ]


def setup_service():

    service, db = make_service()

    company = Mock()
    company.id = 1
    company.symbol = "AAPL"

    prices = make_prices()

    service.company_repo.get_by_symbol.return_value = company
    service.price_repo.get_for_company.return_value = prices

    return service, db, company, prices


# ------------------------------------------------------------------
# COMMON DATA ACCESS
# ------------------------------------------------------------------


def test_get_prices_returns_company_prices():

    service, db, company, prices = setup_service()

    result = service._get_prices("AAPL")

    assert result == prices

    service.company_repo.get_by_symbol.assert_called_once_with(
        "AAPL"
    )

    service.price_repo.get_for_company.assert_called_once_with(
        1
    )


def test_get_prices_company_not_found():

    service, db = make_service()

    service.company_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ValueError,
        match="AAPL not found.",
    ):
        service._get_prices("AAPL")

    service.price_repo.get_for_company.assert_not_called()


# ------------------------------------------------------------------
# SMA
# ------------------------------------------------------------------


def test_sma_calls_indicator_and_returns_result(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 101.5]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.MovingAverage.sma",
        mocked,
    )

    result = service.sma("AAPL", period=20)

    mocked.assert_called_once_with(
        [102.0, 106.0],
        20,
    )

    assert result == [
        {
            "date": prices[0].date,
            "close": 102.0,
            "sma": None,
        },
        {
            "date": prices[1].date,
            "close": 106.0,
            "sma": 101.5,
        },
    ]


# ------------------------------------------------------------------
# EMA
# ------------------------------------------------------------------


def test_ema_calls_indicator_and_returns_result(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 104.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.ExponentialMovingAverage.ema",
        mocked,
    )

    result = service.ema("AAPL", period=20)

    mocked.assert_called_once_with(
        [102.0, 106.0],
        20,
    )

    assert result[0]["ema"] is None
    assert result[1]["ema"] == 104.0


# ------------------------------------------------------------------
# MACD
# ------------------------------------------------------------------


def test_macd_calls_indicator_and_returns_result(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "macd": None,
            "signal": None,
            "histogram": None,
        },
        {
            "macd": 1.5,
            "signal": 1.0,
            "histogram": 0.5,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.MACD.macd",
        mocked,
    )

    result = service.macd("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0]
    )

    assert result[1] == {
        "date": prices[1].date,
        "close": 106.0,
        "macd": 1.5,
        "signal": 1.0,
        "histogram": 0.5,
    }


# ------------------------------------------------------------------
# RSI
# ------------------------------------------------------------------


def test_rsi_calls_indicator_and_returns_result(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 65.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.RelativeStrengthIndex.rsi",
        mocked,
    )

    result = service.rsi(
        "AAPL",
        period=14,
    )

    mocked.assert_called_once_with(
        [102.0, 106.0],
        14,
    )

    assert result[1]["rsi"] == 65.0


# ------------------------------------------------------------------
# BOLLINGER
# ------------------------------------------------------------------


def test_bollinger_calls_indicator_and_returns_result(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "middle": None,
            "upper": None,
            "lower": None,
        },
        {
            "middle": 104.0,
            "upper": 110.0,
            "lower": 98.0,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.BollingerBands.calculate",
        mocked,
    )

    result = service.bollinger(
        "AAPL",
        period=20,
    )

    mocked.assert_called_once_with(
        [102.0, 106.0],
        20,
    )

    assert result[1]["middle"] == 104.0
    assert result[1]["upper"] == 110.0
    assert result[1]["lower"] == 98.0


# ------------------------------------------------------------------
# OHLC INDICATORS
# ------------------------------------------------------------------


def test_atr_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 4.5]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.AverageTrueRange.atr",
        mocked,
    )

    result = service.atr("AAPL", period=14)

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        14,
    )

    assert result[1]["atr"] == 4.5


def test_adx_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 25.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.AverageDirectionalIndex.adx",
        mocked,
    )

    result = service.adx("AAPL", period=14)

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        14,
    )

    assert result[1]["adx"] == 25.0


def test_supertrend_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 103.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.Supertrend.calculate",
        mocked,
    )

    result = service.supertrend(
        "AAPL",
        period=10,
        multiplier=3.0,
    )

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        10,
        3.0,
    )

    assert result[1]["supertrend"] == 103.0


def test_stochastic_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {"k": None, "d": None},
        {"k": 80.0, "d": 75.0},
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.StochasticOscillator.calculate",
        mocked,
    )

    result = service.stochastic("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        14,
        3,
    )

    assert result[1]["k"] == 80.0
    assert result[1]["d"] == 75.0


def test_parabolic_sar_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [99.0, 101.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.ParabolicSAR.calculate",
        mocked,
    )

    result = service.parabolic_sar("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
    )

    assert result[1]["psar"] == 101.0


# ------------------------------------------------------------------
# VOLUME INDICATORS
# ------------------------------------------------------------------


def test_vwap_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [100.0, 104.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.VolumeWeightedAveragePrice.calculate",
        mocked,
    )

    result = service.vwap("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        [1_000_000, 1_200_000],
    )

    assert result[1]["vwap"] == 104.0
    assert result[1]["volume"] == 1_200_000


def test_obv_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [0, 1_200_000]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.OnBalanceVolume.calculate",
        mocked,
    )

    result = service.obv("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        [1_000_000, 1_200_000],
    )

    assert result[1]["obv"] == 1_200_000


def test_mfi_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 60.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.MoneyFlowIndex.calculate",
        mocked,
    )

    result = service.mfi("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        [1_000_000, 1_200_000],
        14,
    )

    assert result[1]["mfi"] == 60.0


def test_cmf_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 0.25]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.ChaikinMoneyFlow.calculate",
        mocked,
    )

    result = service.cmf("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        [1_000_000, 1_200_000],
        20,
    )

    assert result[1]["cmf"] == 0.25


# ------------------------------------------------------------------
# CHANNEL / OSCILLATOR INDICATORS
# ------------------------------------------------------------------


def test_ichimoku_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "tenkan": None,
            "kijun": None,
            "span_a": None,
            "span_b": None,
        },
        {
            "tenkan": 103.0,
            "kijun": 102.0,
            "span_a": 104.0,
            "span_b": 101.0,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.IchimokuCloud.calculate",
        mocked,
    )

    result = service.ichimoku("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
    )

    assert result[1]["tenkan"] == 103.0
    assert result[1]["kijun"] == 102.0
    assert result[1]["span_a"] == 104.0
    assert result[1]["span_b"] == 101.0


def test_donchian_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "upper": None,
            "middle": None,
            "lower": None,
        },
        {
            "upper": 110.0,
            "middle": 104.0,
            "lower": 98.0,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.DonchianChannels.calculate",
        mocked,
    )

    result = service.donchian("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        20,
    )

    assert result[1]["upper"] == 110.0


def test_keltner_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "middle": None,
            "upper": None,
            "lower": None,
        },
        {
            "middle": 104.0,
            "upper": 110.0,
            "lower": 98.0,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.KeltnerChannels.calculate",
        mocked,
    )

    result = service.keltner("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        20,
        2.0,
    )

    assert result[1]["middle"] == 104.0


def test_cci_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 120.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.CommodityChannelIndex.calculate",
        mocked,
    )

    result = service.cci("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        20,
    )

    assert result[1]["cci"] == 120.0


def test_williams_r_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, -20.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.WilliamsR.calculate",
        mocked,
    )

    result = service.williams_r("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        14,
    )

    assert result[1]["williams_r"] == -20.0


def test_roc_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 4.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.RateOfChange.calculate",
        mocked,
    )

    result = service.roc("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        12,
    )

    assert result[1]["roc"] == 4.0


def test_ultimate_oscillator_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 70.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.UltimateOscillator.calculate",
        mocked,
    )

    result = service.ultimate_oscillator("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        7,
        14,
        28,
    )

    assert result[1]["ultimate_oscillator"] == 70.0


def test_trix_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 2.5]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.TRIX.calculate",
        mocked,
    )

    result = service.trix("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        15,
    )

    assert result[1]["trix"] == 2.5


def test_aroon_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "aroon_up": None,
            "aroon_down": None,
        },
        {
            "aroon_up": 80.0,
            "aroon_down": 20.0,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.Aroon.calculate",
        mocked,
    )

    result = service.aroon("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        25,
    )

    assert result[1]["aroon_up"] == 80.0
    assert result[1]["aroon_down"] == 20.0


def test_aroon_oscillator_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 60.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.AroonOscillator.calculate",
        mocked,
    )

    result = service.aroon_oscillator("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        25,
    )

    assert result[1]["aroon_oscillator"] == 60.0


def test_dpo_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 1.5]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.DetrendedPriceOscillator.calculate",
        mocked,
    )

    result = service.dpo("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        20,
    )

    assert result[1]["dpo"] == 1.5


def test_vortex_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "vortex_plus": None,
            "vortex_minus": None,
        },
        {
            "vortex_plus": 1.2,
            "vortex_minus": 0.8,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.VortexIndicator.calculate",
        mocked,
    )

    result = service.vortex("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        14,
    )

    assert result[1]["vortex_plus"] == 1.2
    assert result[1]["vortex_minus"] == 0.8


# ------------------------------------------------------------------
# ADDITIONAL VOLUME INDICATORS
# ------------------------------------------------------------------


def test_emv_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 2.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.EaseOfMovement.emv",
        mocked,
    )

    result = service.emv("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [1_000_000, 1_200_000],
        14,
    )

    assert result[1]["emv"] == 2.0


def test_accumulation_distribution_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [0.0, 500.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.AccumulationDistribution.ad",
        mocked,
    )

    result = service.accumulation_distribution("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        [1_000_000, 1_200_000],
    )

    assert result[1]["accumulation_distribution"] == 500.0


def test_force_index_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [0.0, 4_800_000.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.ForceIndex.force_index",
        mocked,
    )

    result = service.force_index("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        [1_000_000, 1_200_000],
    )

    assert result[1]["force_index"] == 4_800_000.0


def test_nvi_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [1000.0, 1050.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.NegativeVolumeIndex.calculate",
        mocked,
    )

    result = service.nvi("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        [1_000_000, 1_200_000],
    )

    assert result[1]["nvi"] == 1050.0


def test_pvi_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [1000.0, 1050.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.PositiveVolumeIndex.calculate",
        mocked,
    )

    result = service.pvi("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        [1_000_000, 1_200_000],
    )

    assert result[1]["pvi"] == 1050.0


def test_kvo_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "kvo": None,
            "signal": None,
        },
        {
            "kvo": 10.0,
            "signal": 8.0,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.KlingerVolumeOscillator.calculate",
        mocked,
    )

    result = service.kvo("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        [1_000_000, 1_200_000],
        34,
        55,
        13,
    )

    assert result[1]["kvo"] == 10.0
    assert result[1]["signal"] == 8.0


def test_chaikin_oscillator_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 2.5]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.ChaikinOscillator.calculate",
        mocked,
    )

    result = service.chaikin_oscillator("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        [1_000_000, 1_200_000],
        3,
        10,
    )

    assert result[1]["chaikin_oscillator"] == 2.5


# ------------------------------------------------------------------
# TREND / MOMENTUM
# ------------------------------------------------------------------


def test_elder_ray_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [
        {
            "bull_power": None,
            "bear_power": None,
        },
        {
            "bull_power": 5.0,
            "bear_power": -3.0,
        },
    ]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.ElderRayIndex.calculate",
        mocked,
    )

    result = service.elder_ray("AAPL")

    mocked.assert_called_once_with(
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        13,
    )

    assert result[1]["bull_power"] == 5.0
    assert result[1]["bear_power"] == -3.0


def test_rvi_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 0.75]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.RelativeVigorIndex.calculate",
        mocked,
    )

    result = service.rvi("AAPL")

    mocked.assert_called_once_with(
        [100.0, 102.0],
        [105.0, 108.0],
        [95.0, 99.0],
        [102.0, 106.0],
        10,
    )

    assert result[1]["rvi"] == 0.75


def test_coppock_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 4.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.CoppockCurve.calculate",
        mocked,
    )

    result = service.coppock("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        14,
        11,
        10,
    )

    assert result[1]["coppock"] == 4.0


def test_kst_calls_indicator(monkeypatch):

    service, db, company, prices = setup_service()

    values = [None, 12.0]

    mocked = Mock(return_value=values)

    monkeypatch.setattr(
        "quantcore.services.analytics_service.KnowSureThing.calculate",
        mocked,
    )

    result = service.kst("AAPL")

    mocked.assert_called_once_with(
        [102.0, 106.0],
        10,
        15,
        20,
        30,
        10,
        10,
        10,
        15,
    )

    assert result[1]["kst"] == 12.0