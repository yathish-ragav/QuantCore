from datetime import datetime

from pydantic import BaseModel, Field

from quantcore.core.enums import PriceBasis


class PriceData(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float | None = None
    price_basis: PriceBasis = PriceBasis.UNADJUSTED
    volume: int
    dividends: float = 0.0
    stock_splits: float = 0.0
    source_reference: str | None = Field(default=None, max_length=1000)
