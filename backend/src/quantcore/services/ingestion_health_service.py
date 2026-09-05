from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.services.ingestion_orchestrator import (
    FreshnessView,
    IngestionOrchestrator,
)


class IngestionHealthStatus(str, Enum):
    """Operational health state derived from ingestion freshness state."""

    HEALTHY = "HEALTHY"
    STALE = "STALE"
    FAILED = "FAILED"
    NEVER_INGESTED = "NEVER_INGESTED"


@dataclass(frozen=True)
class IngestionHealthView:
    """Deterministic health assessment for one dataset/entity."""

    dataset: IngestionDataset
    scope: IngestionScope
    status: IngestionHealthStatus
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_success_source: str | None
    last_success_records: int
    consecutive_failures: int
    last_error: str | None

    @property
    def is_healthy(self) -> bool:
        return self.status is IngestionHealthStatus.HEALTHY


class IngestionHealthService:
    """Classify ingestion operational health without mutating ingestion state."""

    _SEVERITY = {
        IngestionHealthStatus.HEALTHY: 0,
        IngestionHealthStatus.STALE: 1,
        IngestionHealthStatus.FAILED: 2,
        IngestionHealthStatus.NEVER_INGESTED: 3,
    }

    def __init__(self, db):
        self._orchestrator = IngestionOrchestrator(db)

    @classmethod
    def _status(cls, view: FreshnessView) -> IngestionHealthStatus:
        if view.last_success_at is None:
            if view.consecutive_failures > 0:
                return IngestionHealthStatus.FAILED
            return IngestionHealthStatus.NEVER_INGESTED

        if view.consecutive_failures > 0:
            if (
                view.last_attempt_at is None
                or view.last_attempt_at >= view.last_success_at
            ):
                return IngestionHealthStatus.FAILED

        if not view.is_fresh:
            return IngestionHealthStatus.STALE

        return IngestionHealthStatus.HEALTHY

    @classmethod
    def _view(cls, freshness: FreshnessView) -> IngestionHealthView:
        return IngestionHealthView(
            dataset=freshness.dataset,
            scope=freshness.scope,
            status=cls._status(freshness),
            last_attempt_at=freshness.last_attempt_at,
            last_success_at=freshness.last_success_at,
            last_success_source=freshness.last_success_source,
            last_success_records=freshness.last_success_records,
            consecutive_failures=freshness.consecutive_failures,
            last_error=freshness.last_error,
        )

    def assess(self, symbol: str) -> tuple[IngestionHealthView, ...]:
        """Return deterministic health for every registered dataset of a symbol."""
        symbol = symbol.strip().upper()
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        freshness = self._orchestrator.get_freshness(symbol)
        return tuple(self._view(view) for view in freshness)

    def overall_status(
        self,
        views: tuple[IngestionHealthView, ...],
    ) -> IngestionHealthStatus:
        """Return the worst status across a symbol's dataset health views."""
        if not views:
            return IngestionHealthStatus.NEVER_INGESTED

        return max(
            (view.status for view in views),
            key=self._SEVERITY.__getitem__,
        )
