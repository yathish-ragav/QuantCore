from dataclasses import dataclass
from datetime import datetime

from quantcore.core.enums import SecurityType


@dataclass(frozen=True)
class UniverseCompany:
    cik: str
    symbol: str
    name: str
    exchange: str


@dataclass(frozen=True)
class UniverseSecurityClassification:
    cik: str
    symbol: str
    security_type: SecurityType
    source: str
    observed_at: datetime
    source_reference: str
    provider_type: str | None = None
