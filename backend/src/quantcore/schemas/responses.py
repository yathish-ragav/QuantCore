from datetime import date, datetime

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


class IncomeStatementResponse(BaseModel):
    fiscal_date: date
    total_revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    eps: float | None = None
    shares_outstanding: int | None = None


class IncomeStatementSyncResponse(BaseModel):
    symbol: str
    statements_added: int


class CashFlowStatementResponse(BaseModel):
    fiscal_date: date
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    free_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    depreciation_and_amortization: float | None = None
    stock_based_compensation: float | None = None
    dividends_paid: float | None = None
    share_repurchases: float | None = None
    net_change_in_cash: float | None = None


class CashFlowStatementSyncResponse(BaseModel):
    symbol: str
    statements_added: int


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