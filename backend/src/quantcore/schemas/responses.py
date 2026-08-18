from datetime import datetime

from pydantic import BaseModel


class CompanyResponse(BaseModel):
    id: int
    symbol: str
    name: str
    sector: str
    industry: str
    country: str
    website: str
    market_cap: int | None = None


class PriceResponse(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    dividends: float
    stock_splits: float


class NewsResponse(BaseModel):
    title: str
    publisher: str
    summary: str
    url: str
    published_at: datetime | None = None


class NewsSyncResponse(BaseModel):
    symbol: str
    articles_added: int