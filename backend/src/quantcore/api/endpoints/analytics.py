from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from quantcore.db.database import get_db
from quantcore.services.analytics_service import AnalyticsService

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get("/sma/{symbol}")
def get_sma(
    symbol: str,
    period: int = 20,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.sma(
        symbol=symbol,
        period=period,
    )


@router.get("/ema/{symbol}")
def get_ema(
    symbol: str,
    period: int = 20,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.ema(
        symbol=symbol,
        period=period,
    )


@router.get("/macd/{symbol}")
def get_macd(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.macd(symbol)


@router.get("/rsi/{symbol}")
def get_rsi(
    symbol: str,
    period: int = 14,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.rsi(
        symbol=symbol,
        period=period,
    )


@router.get("/bollinger/{symbol}")
def get_bollinger(
    symbol: str,
    period: int = 20,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.bollinger(
        symbol=symbol,
        period=period,
    )


@router.get("/atr/{symbol}")
def get_atr(
    symbol: str,
    period: int = 14,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.atr(
        symbol=symbol,
        period=period,
    )


@router.get("/adx/{symbol}")
def get_adx(
    symbol: str,
    period: int = 14,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.adx(
        symbol=symbol,
        period=period,
    )


@router.get("/supertrend/{symbol}")
def get_supertrend(
    symbol: str,
    period: int = 10,
    multiplier: float = 3.0,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.supertrend(
        symbol=symbol,
        period=period,
        multiplier=multiplier,
    )


@router.get("/stochastic/{symbol}")
def get_stochastic(
    symbol: str,
    period: int = 14,
    signal_period: int = 3,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.stochastic(
        symbol=symbol,
        period=period,
        signal_period=signal_period,
    )


@router.get("/psar/{symbol}")
def get_psar(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.parabolic_sar(symbol)


@router.get("/vwap/{symbol}")
def get_vwap(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.vwap(symbol)


@router.get("/obv/{symbol}")
def get_obv(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.obv(symbol)

@router.get("/mfi/{symbol}")
def get_mfi(
    symbol: str,
    period: int = 14,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.mfi(
        symbol=symbol,
        period=period,
    )

@router.get("/cmf/{symbol}")
def get_cmf(
    symbol: str,
    period: int = 20,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.cmf(
        symbol=symbol,
        period=period,
    )

@router.get("/ichimoku/{symbol}")
def get_ichimoku(
    symbol: str,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.ichimoku(symbol)

@router.get("/donchian/{symbol}")
def get_donchian(
    symbol: str,
    period: int = 20,
    db: Session = Depends(get_db),
):
    service = AnalyticsService(db)

    return service.donchian(
        symbol=symbol,
        period=period,
    )

@router.get("/keltner/{symbol}")
def get_keltner(
    symbol: str,
    period: int = 20,
    multiplier: float = 2.0,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.keltner(
        symbol,
        period,
        multiplier,
    )

@router.get("/cci/{symbol}")
def get_cci(
    symbol: str,
    period: int = 20,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.cci(
        symbol,
        period,
    )

@router.get("/williams-r/{symbol}")
def get_williams_r(
    symbol: str,
    period: int = 14,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.williams_r(
        symbol,
        period,
    )

@router.get("/roc/{symbol}")
def get_roc(
    symbol: str,
    period: int = 12,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.roc(
        symbol,
        period,
    )

@router.get("/ultimate-oscillator/{symbol}")
def get_ultimate_oscillator(
    symbol: str,
    short_period: int = 7,
    medium_period: int = 14,
    long_period: int = 28,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.ultimate_oscillator(
        symbol,
        short_period,
        medium_period,
        long_period,
    )

@router.get("/trix/{symbol}")
def get_trix(
    symbol: str,
    period: int = 15,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.trix(
        symbol,
        period,
    )

@router.get("/aroon/{symbol}")
def get_aroon(
    symbol: str,
    period: int = 25,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.aroon(
        symbol,
        period,
    )

@router.get("/aroon-oscillator/{symbol}")
def get_aroon_oscillator(
    symbol: str,
    period: int = 25,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.aroon_oscillator(
        symbol,
        period,
    )

@router.get("/dpo/{symbol}")
def get_dpo(
    symbol: str,
    period: int = 20,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.dpo(
        symbol,
        period,
    )

@router.get("/vortex/{symbol}")
def get_vortex(
    symbol: str,
    period: int = 14,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.vortex(
        symbol,
        period,
    )