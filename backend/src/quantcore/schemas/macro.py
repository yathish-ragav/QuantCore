from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MacroSeriesData(BaseModel):
    series_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    frequency: str = Field(min_length=1, max_length=100)
    frequency_short: str | None = Field(default=None, max_length=20)
    units: str = Field(min_length=1, max_length=255)
    units_short: str | None = Field(default=None, max_length=100)
    seasonal_adjustment: str | None = Field(default=None, max_length=100)
    seasonal_adjustment_short: str | None = Field(default=None, max_length=20)
    observation_start: date | None = None
    observation_end: date | None = None
    last_updated: datetime | None = None
    notes: str | None = None


class MacroObservationData(BaseModel):
    series_id: str = Field(min_length=1, max_length=100)
    observation_date: date
    value: Decimal | None = None
    realtime_start: date
    realtime_end: date
    vintage_date: date
