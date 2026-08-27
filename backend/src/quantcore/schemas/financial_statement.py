from datetime import date

from pydantic import BaseModel, Field

from quantcore.core.enums import FinancialPeriodType


class FinancialStatementMetadata(BaseModel):
    """Temporal and filing identity shared by financial statements."""

    period_start: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    fiscal_period: str | None = None
    period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL
    filing_date: date | None = None
    filing_form: str | None = None
    accession_number: str | None = None
