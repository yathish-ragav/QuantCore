from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from quantcore.db.database import get_db
from quantcore.services.price_service import PriceService

router = APIRouter(
    prefix="/prices",
)


@router.get("/{symbol}")
def get_prices(
    symbol: str,
    db: Session = Depends(get_db),
):

    service = PriceService(db)

    prices = service.get_price_history(
        symbol.upper()
    )

    return [
        {
            "date": price.date,
            "open": price.open,
            "high": price.high,
            "low": price.low,
            "close": price.close,
            "volume": price.volume,
            "dividends": price.dividends,
            "stock_splits": price.stock_splits,
        }
        for price in prices
    ]