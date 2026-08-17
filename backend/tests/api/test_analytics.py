from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from quantcore.api.main import app


client = TestClient(app)


def make_service():
    service = Mock()

    service.sma.return_value = []
    service.ema.return_value = []
    service.macd.return_value = []
    service.rsi.return_value = []
    service.bollinger.return_value = []
    service.atr.return_value = []
    service.adx.return_value = []
    service.supertrend.return_value = []
    service.stochastic.return_value = []
    service.parabolic_sar.return_value = []
    service.vwap.return_value = []
    service.obv.return_value = []
    service.mfi.return_value = []
    service.cmf.return_value = []
    service.ichimoku.return_value = []
    service.donchian.return_value = []
    service.keltner.return_value = []
    service.cci.return_value = []
    service.williams_r.return_value = []
    service.roc.return_value = []
    service.ultimate_oscillator.return_value = []
    service.trix.return_value = []
    service.aroon.return_value = []
    service.aroon_oscillator.return_value = []
    service.dpo.return_value = []
    service.vortex.return_value = []
    service.emv.return_value = []
    service.accumulation_distribution.return_value = []
    service.force_index.return_value = []
    service.nvi.return_value = []
    service.pvi.return_value = []
    service.kvo.return_value = []
    service.chaikin_oscillator.return_value = []
    service.elder_ray.return_value = []
    service.rvi.return_value = []
    service.coppock.return_value = []
    service.kst.return_value = []

    return service


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_sma_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/sma/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.sma.assert_called_once_with(
        symbol="AAPL",
        period=20,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_ema_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/ema/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.ema.assert_called_once_with(
        symbol="AAPL",
        period=20,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_macd_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/macd/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.macd.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_rsi_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/rsi/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.rsi.assert_called_once_with(
        symbol="AAPL",
        period=14,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_bollinger_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/bollinger/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.bollinger.assert_called_once_with(
        symbol="AAPL",
        period=20,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_atr_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/atr/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.atr.assert_called_once_with(
        symbol="AAPL",
        period=14,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_adx_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/adx/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.adx.assert_called_once_with(
        symbol="AAPL",
        period=14,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_supertrend_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/supertrend/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.supertrend.assert_called_once_with(
        symbol="AAPL",
        period=10,
        multiplier=3.0,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_stochastic_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/stochastic/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.stochastic.assert_called_once_with(
        symbol="AAPL",
        period=14,
        signal_period=3,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_psar_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/psar/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.parabolic_sar.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_vwap_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/vwap/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.vwap.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_obv_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/obv/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.obv.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_mfi_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/mfi/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.mfi.assert_called_once_with(
        symbol="AAPL",
        period=14,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_cmf_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/cmf/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.cmf.assert_called_once_with(
        symbol="AAPL",
        period=20,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_ichimoku_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/ichimoku/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.ichimoku.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_donchian_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/donchian/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.donchian.assert_called_once_with(
        symbol="AAPL",
        period=20,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_keltner_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/keltner/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.keltner.assert_called_once_with(
        "AAPL",
        20,
        2.0,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_cci_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/cci/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.cci.assert_called_once_with(
        "AAPL",
        20,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_williams_r_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/williams-r/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.williams_r.assert_called_once_with(
        "AAPL",
        14,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_roc_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/roc/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.roc.assert_called_once_with(
        "AAPL",
        12,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_ultimate_oscillator_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/ultimate-oscillator/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.ultimate_oscillator.assert_called_once_with(
        "AAPL",
        7,
        14,
        28,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_trix_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/trix/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.trix.assert_called_once_with(
        "AAPL",
        15,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_aroon_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/aroon/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.aroon.assert_called_once_with(
        "AAPL",
        25,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_aroon_oscillator_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/aroon-oscillator/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.aroon_oscillator.assert_called_once_with(
        "AAPL",
        25,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_dpo_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/dpo/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.dpo.assert_called_once_with(
        "AAPL",
        20,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_vortex_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/vortex/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.vortex.assert_called_once_with(
        "AAPL",
        14,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_emv_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/emv/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.emv.assert_called_once_with(
        "AAPL",
        14,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_accumulation_distribution_endpoint(
    mock_service,
):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/accumulation-distribution/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.accumulation_distribution.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_force_index_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/force-index/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.force_index.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_nvi_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/nvi/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.nvi.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_pvi_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/pvi/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.pvi.assert_called_once_with(
        "AAPL"
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_kvo_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/kvo/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.kvo.assert_called_once_with(
        "AAPL",
        34,
        55,
        13,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_chaikin_oscillator_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/chaikin-oscillator/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.chaikin_oscillator.assert_called_once_with(
        "AAPL",
        3,
        10,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_elder_ray_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/elder-ray/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.elder_ray.assert_called_once_with(
        "AAPL",
        13,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_rvi_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/rvi/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.rvi.assert_called_once_with(
        "AAPL",
        10,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_coppock_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/coppock/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.coppock.assert_called_once_with(
        "AAPL",
        14,
        11,
        10,
    )


@patch(
    "quantcore.api.dependencies.AnalyticsService"
)
def test_kst_endpoint(mock_service):

    service = make_service()
    mock_service.return_value = service

    response = client.get(
        "/analytics/kst/AAPL"
    )

    assert response.status_code == 200
    assert response.json() == []

    service.kst.assert_called_once_with(
        "AAPL",
        10,
        15,
        20,
        30,
        10,
        10,
        10,
        15,
    )