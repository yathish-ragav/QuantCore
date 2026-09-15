from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarketIndexResponse(BaseModel):
    id: int
    key: str
    name: str
    provider: str
    methodology_reference: str | None
    source_reference: str | None
    is_active: bool


class IndexConstituentResponse(BaseModel):
    security_id: int
    symbol: str
    exchange: str
    company_id: int
    effective_from: date
    effective_to: date | None
    weight: Decimal | None
    source_reference: str | None
    known_at: datetime
    observed_at: datetime


class ResearchUniverseResponse(BaseModel):
    index_key: str
    as_of: datetime
    security_ids: list[int]
    fingerprint: str
    size: int


class IndexListResponse(BaseModel):
    indexes: list[MarketIndexResponse]
