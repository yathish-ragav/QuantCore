from pydantic import BaseModel


class CompanyData(BaseModel):
    symbol: str
    name: str
    sector: str
    industry: str
    country: str
    website: str
    market_cap: int | None = None