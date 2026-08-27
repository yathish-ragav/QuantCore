from quantcore.core.enums import CorporateActionType, PriceBasis
from datetime import date, datetime

from pydantic import BaseModel, Field

from quantcore.core.enums import FinancialPeriodType


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
    adjusted_close: float | None = None
    price_basis: PriceBasis = PriceBasis.UNADJUSTED
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
    period_start: date | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL
    filing_date: date | None = None
    filing_form: str | None = None
    accession_number: str | None = None
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
    statements_updated: int = 0
    statements_unchanged: int = 0
    records_processed: int = 0


class CashFlowStatementResponse(BaseModel):
    period_start: date | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL
    filing_date: date | None = None
    filing_form: str | None = None
    accession_number: str | None = None
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
    statements_updated: int = 0
    statements_unchanged: int = 0
    records_processed: int = 0



class BalanceSheetResponse(BaseModel):
    period_start: date | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL
    filing_date: date | None = None
    filing_form: str | None = None
    accession_number: str | None = None
    fiscal_date: date
    cash_and_cash_equivalents: float | None = None
    short_term_investments: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    total_current_assets: float | None = None
    property_plant_equipment_net: float | None = None
    goodwill: float | None = None
    intangible_assets: float | None = None
    total_assets: float | None = None
    accounts_payable: float | None = None
    short_term_debt: float | None = None
    total_current_liabilities: float | None = None
    long_term_debt: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    retained_earnings: float | None = None
    total_debt: float | None = None
    net_debt: float | None = None
    working_capital: float | None = None


class BalanceSheetSyncResponse(BaseModel):
    symbol: str
    statements_added: int
    statements_updated: int = 0
    statements_unchanged: int = 0
    records_processed: int = 0


class IngestionFreshnessResponse(BaseModel):
    dataset: str
    scope: str
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_success_source: str | None = None
    last_success_records: int = 0
    consecutive_failures: int = 0
    last_error: str | None = None
    is_fresh: bool


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

class SECFilingResponse(BaseModel):
    accession_number: str
    filing_date: date
    report_date: date | None = None
    acceptance_datetime: datetime | None = None
    form: str
    act: str | None = None
    file_number: str | None = None
    film_number: str | None = None
    items: str | None = None
    primary_document: str | None = None
    primary_doc_description: str | None = None
    is_xbrl: bool
    is_inline_xbrl: bool
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    is_amendment: bool
    filing_url: str | None = None


class FilingEventResponse(BaseModel):
    accession_number: str
    event_type: str
    occurred_at: datetime


class SECFilingSyncResponse(BaseModel):
    symbol: str
    filings_added: int
    filings_updated: int = 0
    filings_unchanged: int = 0
    filings_processed: int = 0
    events_added: int = 0


class CorporateActionResponse(BaseModel):
    effective_date: date
    action_type: CorporateActionType
    amount: float | None = None
    split_ratio: float | None = None


class MacroSeriesResponse(BaseModel):
    series_id: str
    title: str
    frequency: str
    frequency_short: str | None = None
    units: str
    units_short: str | None = None
    seasonal_adjustment: str | None = None
    seasonal_adjustment_short: str | None = None
    observation_start: date | None = None
    observation_end: date | None = None
    last_updated: datetime | None = None


class MacroObservationResponse(BaseModel):
    observation_date: date
    value: float | None = None
    realtime_start: date
    realtime_end: date
    vintage_date: date


class MacroSyncResponse(BaseModel):
    series_id: str
    created: int
    unchanged: int
    records_processed: int
    vintage_date: date


class MacroIngestionFreshnessResponse(BaseModel):
    source: str
    series_id: str
    max_age_seconds: int
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_success_vintage: date | None = None
    last_success_records: int
    consecutive_failures: int
    last_error: str | None = None
    is_fresh: bool


class MacroIngestionSyncResponse(BaseModel):
    series_id: str
    attempted: bool
    succeeded: bool
    skipped: bool
    records_processed: int
    vintage_date: date | None = None
    error: str | None = None
