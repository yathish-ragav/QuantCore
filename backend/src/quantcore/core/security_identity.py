from enum import Enum


class SecurityIdentifierType(str, Enum):
    """Canonical external identifier namespaces used to resolve securities."""

    CUSIP = "CUSIP"
    ISIN = "ISIN"
    SEDOL = "SEDOL"
    FIGI = "FIGI"
    LEI = "LEI"
    VENDOR = "VENDOR"
