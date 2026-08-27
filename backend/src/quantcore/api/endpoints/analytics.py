from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_analytics_service
from quantcore.services.analytics_service import AnalyticsService


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


def normalize_symbol(symbol: str) -> str:
    """
    Normalize equity symbols at the API boundary.
    """
    return symbol.strip().upper()


@router.get("/sma/{symbol}")
def get_sma(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=20, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.sma(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/ema/{symbol}")
def get_ema(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=20, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.ema(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/macd/{symbol}")
def get_macd(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.macd(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/rsi/{symbol}")
def get_rsi(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=14, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.rsi(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/bollinger/{symbol}")
def get_bollinger(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=20, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.bollinger(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/atr/{symbol}")
def get_atr(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=14, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.atr(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/adx/{symbol}")
def get_adx(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=14, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.adx(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/supertrend/{symbol}")
def get_supertrend(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=10, gt=0),
    multiplier: float = Query(default=3.0, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.supertrend(
        symbol=normalize_symbol(symbol),
        period=period,
        multiplier=multiplier,
        as_of=as_of,
    )


@router.get("/stochastic/{symbol}")
def get_stochastic(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=14, gt=0),
    signal_period: int = Query(default=3, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.stochastic(
        symbol=normalize_symbol(symbol),
        period=period,
        signal_period=signal_period,
        as_of=as_of,
    )


@router.get("/psar/{symbol}")
def get_psar(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.parabolic_sar(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/vwap/{symbol}")
def get_vwap(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.vwap(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/obv/{symbol}")
def get_obv(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.obv(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/mfi/{symbol}")
def get_mfi(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=14, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.mfi(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/cmf/{symbol}")
def get_cmf(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=20, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.cmf(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/ichimoku/{symbol}")
def get_ichimoku(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.ichimoku(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/donchian/{symbol}")
def get_donchian(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=20, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.donchian(
        symbol=normalize_symbol(symbol),
        period=period,
        as_of=as_of,
    )


@router.get("/keltner/{symbol}")
def get_keltner(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=20, gt=0),
    multiplier: float = Query(default=2.0, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.keltner(
        normalize_symbol(symbol),
        period,
        multiplier,
        as_of=as_of,
    )


@router.get("/cci/{symbol}")
def get_cci(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=20, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.cci(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/williams-r/{symbol}")
def get_williams_r(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=14, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.williams_r(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/roc/{symbol}")
def get_roc(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=12, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.roc(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/ultimate-oscillator/{symbol}")
def get_ultimate_oscillator(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    short_period: int = Query(default=7, gt=0),
    medium_period: int = Query(default=14, gt=0),
    long_period: int = Query(default=28, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.ultimate_oscillator(
        normalize_symbol(symbol),
        short_period,
        medium_period,
        long_period,
        as_of=as_of,
    )


@router.get("/trix/{symbol}")
def get_trix(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=15, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.trix(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/aroon/{symbol}")
def get_aroon(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=25, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.aroon(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/aroon-oscillator/{symbol}")
def get_aroon_oscillator(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=25, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.aroon_oscillator(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/dpo/{symbol}")
def get_dpo(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=20, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.dpo(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/vortex/{symbol}")
def get_vortex(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=14, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.vortex(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/emv/{symbol}")
def get_emv(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=14, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.emv(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/accumulation-distribution/{symbol}")
def get_accumulation_distribution(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.accumulation_distribution(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/force-index/{symbol}")
def force_index(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.force_index(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/nvi/{symbol}")
def nvi(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.nvi(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/pvi/{symbol}")
def pvi(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.pvi(
        normalize_symbol(symbol),
        as_of=as_of,
    )


@router.get("/kvo/{symbol}")
def kvo(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    fast_period: int = Query(default=34, gt=0),
    slow_period: int = Query(default=55, gt=0),
    signal_period: int = Query(default=13, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.kvo(
        normalize_symbol(symbol),
        fast_period,
        slow_period,
        signal_period,
        as_of=as_of,
    )


@router.get("/chaikin-oscillator/{symbol}")
def chaikin_oscillator(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    fast_period: int = Query(default=3, gt=0),
    slow_period: int = Query(default=10, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.chaikin_oscillator(
        normalize_symbol(symbol),
        fast_period,
        slow_period,
        as_of=as_of,
    )


@router.get("/elder-ray/{symbol}")
def elder_ray(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=13, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.elder_ray(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/rvi/{symbol}")
def rvi(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    period: int = Query(default=10, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.rvi(
        normalize_symbol(symbol),
        period,
        as_of=as_of,
    )


@router.get("/coppock/{symbol}")
def coppock(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    roc_fast_period: int = Query(default=14, gt=0),
    roc_slow_period: int = Query(default=11, gt=0),
    wma_period: int = Query(default=10, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.coppock(
        normalize_symbol(symbol),
        roc_fast_period,
        roc_slow_period,
        wma_period,
        as_of=as_of,
    )


@router.get("/kst/{symbol}")
def kst(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Evaluate the indicator using prices known at this timestamp.",
    ),
    roc1_period: int = Query(default=10, gt=0),
    roc2_period: int = Query(default=15, gt=0),
    roc3_period: int = Query(default=20, gt=0),
    roc4_period: int = Query(default=30, gt=0),
    sma1_period: int = Query(default=10, gt=0),
    sma2_period: int = Query(default=10, gt=0),
    sma3_period: int = Query(default=10, gt=0),
    sma4_period: int = Query(default=15, gt=0),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.kst(
        normalize_symbol(symbol),
        roc1_period,
        roc2_period,
        roc3_period,
        roc4_period,
        sma1_period,
        sma2_period,
        sma3_period,
        sma4_period,
        as_of=as_of,
    )
