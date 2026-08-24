from dataclasses import dataclass
from datetime import timedelta
from enum import Enum


class IngestionDataset(str, Enum):
    """Datasets that QuantCore can refresh through the ingestion coordinator."""

    COMPANY = "company"
    PRICE_HISTORY = "price_history"
    NEWS = "news"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW_STATEMENT = "cash_flow_statement"
    BALANCE_SHEET = "balance_sheet"


class IngestionScope(str, Enum):
    """Database entity scope used by a dataset's freshness state."""

    COMPANY = "company"
    SECURITY = "security"


@dataclass(frozen=True)
class FreshnessPolicy:
    """How long a successful ingestion remains fresh."""

    max_age: timedelta
    description: str


DATASET_POLICIES: dict[IngestionDataset, FreshnessPolicy] = {
    IngestionDataset.COMPANY: FreshnessPolicy(
        max_age=timedelta(days=7),
        description="Company profile metadata is refreshed weekly.",
    ),
    IngestionDataset.PRICE_HISTORY: FreshnessPolicy(
        max_age=timedelta(days=1),
        description="Historical market prices are refreshed daily.",
    ),
    IngestionDataset.NEWS: FreshnessPolicy(
        max_age=timedelta(hours=6),
        description="Company news is refreshed several times per day.",
    ),
    IngestionDataset.INCOME_STATEMENT: FreshnessPolicy(
        max_age=timedelta(days=1),
        description="Fundamentals are checked daily for newly reported filings.",
    ),
    IngestionDataset.CASH_FLOW_STATEMENT: FreshnessPolicy(
        max_age=timedelta(days=1),
        description="Fundamentals are checked daily for newly reported filings.",
    ),
    IngestionDataset.BALANCE_SHEET: FreshnessPolicy(
        max_age=timedelta(days=1),
        description="Fundamentals are checked daily for newly reported filings.",
    ),
}


DATASET_SCOPES: dict[IngestionDataset, IngestionScope] = {
    IngestionDataset.COMPANY: IngestionScope.COMPANY,
    IngestionDataset.PRICE_HISTORY: IngestionScope.SECURITY,
    IngestionDataset.NEWS: IngestionScope.COMPANY,
    IngestionDataset.INCOME_STATEMENT: IngestionScope.COMPANY,
    IngestionDataset.CASH_FLOW_STATEMENT: IngestionScope.COMPANY,
    IngestionDataset.BALANCE_SHEET: IngestionScope.COMPANY,
}
