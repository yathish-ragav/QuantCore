from enum import Enum


class FinancialPeriodType(str, Enum):
    """Canonical period semantics for financial statement observations."""

    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    TTM = "TTM"
    INSTANT = "INSTANT"


class FinancialStatementType(str, Enum):
    """Canonical statement families represented in revision history."""

    INCOME = "INCOME"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"


class FilingEventType(str, Enum):
    """Normalized lifecycle events observed from SEC filing metadata."""

    FILED = "FILED"
    AMENDED = "AMENDED"


class PriceBasis(str, Enum):
    """Adjustment basis of the stored OHLC price fields."""

    UNADJUSTED = "UNADJUSTED"
    ADJUSTED = "ADJUSTED"


class CorporateActionType(str, Enum):
    """Normalized security-level corporate actions."""

    DIVIDEND = "DIVIDEND"
    STOCK_SPLIT = "STOCK_SPLIT"
