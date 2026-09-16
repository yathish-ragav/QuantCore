from pydantic import BaseModel

from quantcore.core.enums import SecurityType


class CompanyData(BaseModel):
    """Normalized company reference data returned by a provider.

    Providers may legitimately omit enrichment fields they do not own or
    publish. The company service preserves existing database values for
    those fields rather than fabricating or erasing them.
    """

    symbol: str
    name: str
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    market_cap: int | None = None
    security_type: SecurityType | None = None
