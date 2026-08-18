from datetime import datetime

from pydantic import BaseModel, Field


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


class APIError(BaseModel):
    code: str = Field(
        ...,
        description="Stable machine-readable error code.",
    )
    message: str = Field(
        ...,
        description="Human-readable error message.",
    )
    request_id: str | None = Field(
        default=None,
        description="Request identifier for tracing and diagnostics.",
    )


class APIErrorResponse(BaseModel):
    error: APIError