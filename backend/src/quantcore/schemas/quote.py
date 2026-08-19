from datetime import datetime

from pydantic import BaseModel


class QuoteData(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    day_low: float | None = None
    day_high: float | None = None
    year_low: float | None = None
    year_high: float | None = None
    market_cap: int | None = None
    price_avg_50: float | None = None
    price_avg_200: float | None = None
    volume: int | None = None
    exchange: str | None = None
    open: float | None = None
    previous_close: float | None = None
    timestamp: datetime
    source: str
