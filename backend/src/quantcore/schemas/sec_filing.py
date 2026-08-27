from datetime import date, datetime

from pydantic import BaseModel, Field

from quantcore.core.enums import FilingEventType


class SECFilingData(BaseModel):
    """Normalized SEC EDGAR filing metadata."""

    accession_number: str = Field(min_length=1, max_length=40)
    filing_date: date
    report_date: date | None = None
    acceptance_datetime: datetime | None = None
    form: str = Field(min_length=1, max_length=20)
    act: str | None = Field(default=None, max_length=20)
    file_number: str | None = Field(default=None, max_length=50)
    film_number: str | None = Field(default=None, max_length=50)
    items: str | None = Field(default=None, max_length=1000)
    primary_document: str | None = Field(default=None, max_length=500)
    primary_doc_description: str | None = Field(default=None, max_length=1000)
    is_xbrl: bool = False
    is_inline_xbrl: bool = False
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    fiscal_period: str | None = Field(default=None, max_length=10)
    is_amendment: bool = False
    filing_url: str | None = Field(default=None, max_length=1000)


class FilingEventData(BaseModel):
    """Normalized lifecycle event for an SEC filing."""

    event_type: FilingEventType
    occurred_at: datetime
