from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseCompany:
    cik: str
    symbol: str
    name: str
    exchange: str