from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.macro_datasets import (
    MACRO_SERIES_POLICIES,
    MacroFreshnessPolicy,
    normalize_series_ids,
)
from quantcore.repositories.macro_ingestion_repository import (
    MacroIngestionStateRepository,
)
from quantcore.services.macro_service import MacroService, MacroSyncResult


@dataclass(frozen=True)
class MacroFreshnessView:
    source: str
    series_id: str
    max_age_seconds: int
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_success_vintage: date | None
    last_success_records: int
    consecutive_failures: int
    last_error: str | None
    is_fresh: bool


@dataclass(frozen=True)
class MacroIngestionResult:
    series_id: str
    attempted: bool
    succeeded: bool
    skipped: bool
    records_processed: int
    vintage_date: date | None
    error: str | None = None


class MacroIngestionOrchestrator:
    """Schedule macro-series refreshes without coupling them to security ingestion."""

    SOURCE = "FRED"

    def __init__(self, db: Session):
        self.db = db
        self.state_repo = MacroIngestionStateRepository(db)

    def _is_fresh(
        self,
        state,
        policy: MacroFreshnessPolicy,
        now: datetime,
    ) -> bool:
        if state is None or state.last_success_at is None:
            return False
        return now - state.last_success_at < policy.max_age

    def get_freshness(
        self,
        series_ids: list[str] | None = None,
    ) -> list[MacroFreshnessView]:
        ids = normalize_series_ids(series_ids)
        if not ids:
            raise InvalidInputError("At least one valid macro series is required.")

        now = datetime.now(timezone.utc)
        views: list[MacroFreshnessView] = []
        for series_id in ids:
            policy = MACRO_SERIES_POLICIES.get(series_id)
            if policy is None:
                raise InvalidInputError(
                    f"Macro series '{series_id}' is not in the managed scheduler registry."
                )
            state = self.state_repo.get(self.SOURCE, series_id)
            views.append(
                MacroFreshnessView(
                    source=self.SOURCE,
                    series_id=series_id,
                    max_age_seconds=int(policy.max_age.total_seconds()),
                    last_attempt_at=state.last_attempt_at if state else None,
                    last_success_at=state.last_success_at if state else None,
                    last_success_vintage=state.last_success_vintage if state else None,
                    last_success_records=state.last_success_records if state else 0,
                    consecutive_failures=state.consecutive_failures if state else 0,
                    last_error=state.last_error if state else None,
                    is_fresh=self._is_fresh(state, policy, now),
                )
            )
        return views

    def sync_series(
        self,
        series_id: str,
        *,
        vintage_date: date | None = None,
        only_stale: bool = True,
    ) -> MacroIngestionResult:
        normalized = series_id.strip().upper()
        if not normalized:
            raise InvalidInputError("Series ID must not be empty.")

        policy = MACRO_SERIES_POLICIES.get(normalized)
        if policy is None:
            raise InvalidInputError(
                f"Macro series '{normalized}' is not in the managed scheduler registry."
            )

        now = datetime.now(timezone.utc)
        state = self.state_repo.get(self.SOURCE, normalized)
        if only_stale and self._is_fresh(state, policy, now):
            return MacroIngestionResult(
                series_id=normalized,
                attempted=False,
                succeeded=False,
                skipped=True,
                records_processed=0,
                vintage_date=state.last_success_vintage,
            )

        state = self.state_repo.get_or_create(self.SOURCE, normalized)
        self.state_repo.mark_attempt(state, now)
        self.db.commit()

        try:
            result: MacroSyncResult = MacroService(self.db).sync_series(
                normalized,
                vintage_date=vintage_date,
            )
            succeeded_at = datetime.now(timezone.utc)
            self.state_repo.mark_success(
                state,
                succeeded_at=succeeded_at,
                vintage_date=result.vintage_date,
                records=result.records_processed,
            )
            self.db.commit()
            return MacroIngestionResult(
                series_id=normalized,
                attempted=True,
                succeeded=True,
                skipped=False,
                records_processed=result.records_processed,
                vintage_date=result.vintage_date,
            )
        except Exception as exc:
            failed_at = datetime.now(timezone.utc)
            self.state_repo.mark_failure(
                state,
                failed_at=failed_at,
                error=str(exc),
            )
            self.db.commit()
            return MacroIngestionResult(
                series_id=normalized,
                attempted=True,
                succeeded=False,
                skipped=False,
                records_processed=0,
                vintage_date=vintage_date,
                error=str(exc),
            )

    def sync_managed(
        self,
        *,
        series_ids: list[str] | None = None,
        only_stale: bool = True,
        limit: int | None = None,
        vintage_date: date | None = None,
    ) -> list[MacroIngestionResult]:
        ids = normalize_series_ids(series_ids)
        if not ids:
            raise InvalidInputError("At least one valid macro series is required.")
        if limit is not None and limit <= 0:
            raise InvalidInputError("Limit must be greater than zero.")
        if limit is not None:
            ids = ids[:limit]

        return [
            self.sync_series(
                series_id,
                vintage_date=vintage_date,
                only_stale=only_stale,
            )
            for series_id in ids
        ]
