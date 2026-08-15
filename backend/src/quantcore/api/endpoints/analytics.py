from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from quantcore.db.database import get_db
from quantcore.services.analytics_service import AnalyticsService


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


def _get_service(db: Session) -> AnalyticsService:
    """
    Construct the analytics service for the current request.

    Keeping service construction in one place prevents every endpoint
    from duplicating the same initialization logic while preserving
    the existing service architecture.
    """
    return AnalyticsService(db)


def _normalize_symbol(symbol: str) -> str:
    """
    Normalize equity symbols at the API boundary.
    """
    return symbol.strip().upper()


@router.get("/sma/{symbol}")
def get_sma(
    symbol: str,
    period: int = Query(default=20, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.sma(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/ema/{symbol}")
def get_ema(
    symbol: str,
    period: int = Query(default=20, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.ema(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/macd/{symbol}")
def get_macd(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.macd(
        _normalize_symbol(symbol)
    )


@router.get("/rsi/{symbol}")
def get_rsi(
    symbol: str,
    period: int = Query(default=14, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.rsi(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/bollinger/{symbol}")
def get_bollinger(
    symbol: str,
    period: int = Query(default=20, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.bollinger(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/atr/{symbol}")
def get_atr(
    symbol: str,
    period: int = Query(default=14, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.atr(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/adx/{symbol}")
def get_adx(
    symbol: str,
    period: int = Query(default=14, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.adx(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/supertrend/{symbol}")
def get_supertrend(
    symbol: str,
    period: int = Query(default=10, gt=0),
    multiplier: float = Query(default=3.0, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.supertrend(
        symbol=_normalize_symbol(symbol),
        period=period,
        multiplier=multiplier,
    )


@router.get("/stochastic/{symbol}")
def get_stochastic(
    symbol: str,
    period: int = Query(default=14, gt=0),
    signal_period: int = Query(default=3, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.stochastic(
        symbol=_normalize_symbol(symbol),
        period=period,
        signal_period=signal_period,
    )


@router.get("/psar/{symbol}")
def get_psar(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.parabolic_sar(
        _normalize_symbol(symbol)
    )


@router.get("/vwap/{symbol}")
def get_vwap(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.vwap(
        _normalize_symbol(symbol)
    )


@router.get("/obv/{symbol}")
def get_obv(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.obv(
        _normalize_symbol(symbol)
    )


@router.get("/mfi/{symbol}")
def get_mfi(
    symbol: str,
    period: int = Query(default=14, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.mfi(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/cmf/{symbol}")
def get_cmf(
    symbol: str,
    period: int = Query(default=20, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.cmf(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/ichimoku/{symbol}")
def get_ichimoku(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.ichimoku(
        _normalize_symbol(symbol)
    )


@router.get("/donchian/{symbol}")
def get_donchian(
    symbol: str,
    period: int = Query(default=20, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.donchian(
        symbol=_normalize_symbol(symbol),
        period=period,
    )


@router.get("/keltner/{symbol}")
def get_keltner(
    symbol: str,
    period: int = Query(default=20, gt=0),
    multiplier: float = Query(default=2.0, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.keltner(
        _normalize_symbol(symbol),
        period,
        multiplier,
    )


@router.get("/cci/{symbol}")
def get_cci(
    symbol: str,
    period: int = Query(default=20, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.cci(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/williams-r/{symbol}")
def get_williams_r(
    symbol: str,
    period: int = Query(default=14, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.williams_r(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/roc/{symbol}")
def get_roc(
    symbol: str,
    period: int = Query(default=12, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.roc(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/ultimate-oscillator/{symbol}")
def get_ultimate_oscillator(
    symbol: str,
    short_period: int = Query(default=7, gt=0),
    medium_period: int = Query(default=14, gt=0),
    long_period: int = Query(default=28, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.ultimate_oscillator(
        _normalize_symbol(symbol),
        short_period,
        medium_period,
        long_period,
    )


@router.get("/trix/{symbol}")
def get_trix(
    symbol: str,
    period: int = Query(default=15, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.trix(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/aroon/{symbol}")
def get_aroon(
    symbol: str,
    period: int = Query(default=25, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.aroon(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/aroon-oscillator/{symbol}")
def get_aroon_oscillator(
    symbol: str,
    period: int = Query(default=25, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.aroon_oscillator(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/dpo/{symbol}")
def get_dpo(
    symbol: str,
    period: int = Query(default=20, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.dpo(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/vortex/{symbol}")
def get_vortex(
    symbol: str,
    period: int = Query(default=14, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.vortex(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/emv/{symbol}")
def get_emv(
    symbol: str,
    period: int = Query(default=14, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.emv(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/accumulation-distribution/{symbol}")
def get_accumulation_distribution(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.accumulation_distribution(
        _normalize_symbol(symbol)
    )


@router.get("/force-index/{symbol}")
def force_index(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.force_index(
        _normalize_symbol(symbol)
    )


@router.get("/nvi/{symbol}")
def nvi(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.nvi(
        _normalize_symbol(symbol)
    )


@router.get("/pvi/{symbol}")
def pvi(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.pvi(
        _normalize_symbol(symbol)
    )


@router.get("/kvo/{symbol}")
def kvo(
    symbol: str,
    fast_period: int = Query(default=34, gt=0),
    slow_period: int = Query(default=55, gt=0),
    signal_period: int = Query(default=13, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.kvo(
        _normalize_symbol(symbol),
        fast_period,
        slow_period,
        signal_period,
    )


@router.get("/chaikin-oscillator/{symbol}")
def chaikin_oscillator(
    symbol: str,
    fast_period: int = Query(default=3, gt=0),
    slow_period: int = Query(default=10, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.chaikin_oscillator(
        _normalize_symbol(symbol),
        fast_period,
        slow_period,
    )


@router.get("/elder-ray/{symbol}")
def elder_ray(
    symbol: str,
    period: int = Query(default=13, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.elder_ray(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/rvi/{symbol}")
def rvi(
    symbol: str,
    period: int = Query(default=10, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.rvi(
        _normalize_symbol(symbol),
        period,
    )


@router.get("/coppock/{symbol}")
def coppock(
    symbol: str,
    roc_fast_period: int = Query(default=14, gt=0),
    roc_slow_period: int = Query(default=11, gt=0),
    wma_period: int = Query(default=10, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.coppock(
        _normalize_symbol(symbol),
        roc_fast_period,
        roc_slow_period,
        wma_period,
    )


@router.get("/kst/{symbol}")
def kst(
    symbol: str,
    roc1_period: int = Query(default=10, gt=0),
    roc2_period: int = Query(default=15, gt=0),
    roc3_period: int = Query(default=20, gt=0),
    roc4_period: int = Query(default=30, gt=0),
    sma1_period: int = Query(default=10, gt=0),
    sma2_period: int = Query(default=10, gt=0),
    sma3_period: int = Query(default=10, gt=0),
    sma4_period: int = Query(default=15, gt=0),
    db: Session = Depends(get_db),
):
    service = _get_service(db)

    return service.kst(
        _normalize_symbol(symbol),
        roc1_period,
        roc2_period,
        roc3_period,
        roc4_period,
        sma1_period,
        sma2_period,
        sma3_period,
        sma4_period,
    )