from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SECXBRLFactObservationData(BaseModel):
    """Immutable SEC CompanyFacts observation preserving filing revisions."""

    taxonomy: str = Field(min_length=1, max_length=50)
    concept: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=100)
    value: Decimal
    period_start: date | None = None
    period_end: date
    filed_at: date
    accession_number: str = Field(min_length=1, max_length=40)
    form: str = Field(min_length=1, max_length=20)
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    fiscal_period: str | None = Field(default=None, max_length=10)
    frame: str = Field(default="", max_length=40)
    qtrs: int = Field(default=0, ge=0, le=100)
    decimals: str | None = Field(default=None, max_length=40)
    accepted_at: datetime | None = None
