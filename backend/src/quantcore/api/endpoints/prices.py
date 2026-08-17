from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_price_service
from quantcore.services.price_service import PriceService


router = APIRouter(
    prefix="/prices",
)


@router.get("/{symbol}")
def get_prices(
    symbol: str,
    service: PriceService = Depends(get_price_service),
):

    prices = service.get_price_history(
        symbol.strip().upper()
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