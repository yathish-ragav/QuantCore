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
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    db: Session = Depends(get_db),
):

    service = AnalyticsService(db)

    return service.macd(
        symbol=symbol,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )

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