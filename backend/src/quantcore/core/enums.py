from enum import Enum


class FinancialPeriodType(str, Enum):
    """Canonical period semantics for financial statement observations."""

    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    TTM = "TTM"
    INSTANT = "INSTANT"
