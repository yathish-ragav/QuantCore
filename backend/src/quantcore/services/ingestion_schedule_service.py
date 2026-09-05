from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.models.ingestion import IngestionJob
from quantcore.models.ingestion_schedule import IngestionSchedule
from quantcore.repositories.ingestion_schedule_repository import IngestionScheduleRepository
from quantcore.repositories.ingestion_state_repository import IngestionStateRepository
from quantcore.services.ingestion_execution_service import IngestionJobView
from quantcore.services.ingestion_orchestrator import IngestionOrchestrator


MIN_INTERVAL_SECONDS = 60
DEFAULT_TRIGGER_BATCH_SIZE = 100


@dataclass(frozen=True)
class IngestionScheduleView:
    """Stable read model for one persistent ingestion schedule."""

    schedule_id: int
    name: str
    dataset: IngestionDataset
    symbols: tuple[str, ...] | None
    target_limit: int | None
    only_stale: bool
    interval_seconds: int
    next_run_at: datetime
    enabled: bool
    last_triggered_at: datetime | None


@dataclass(frozen=True)
class ScheduledIngestionTrigger:
    """The durable job created by one scheduler decision."""

    schedule_id: int
    scheduled_for: datetime
    job: IngestionJobView


class IngestionScheduleService:
    """Turn persistent schedules into durable queued ingestion jobs.

    This is intentionally a trigger layer, not an execution engine. A process
    can call ``trigger_due`` from cron, systemd, Kubernetes, or a future
    scheduler without changing the QuantCore ingestion contract.
    """

    def __init__(self, db: Session, *, orchestrator: IngestionOrchestrator | None = None):
        self.db = db
        self.repository = IngestionScheduleRepository(db)
        self.job_repository = IngestionStateRepository(db)
        self.orchestrator = orchestrator or IngestionOrchestrator(db)

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise InvalidInputError("Schedule name must not be empty.")
        if len(normalized) > 128:
            raise InvalidInputError("Schedule name must be at most 128 characters.")
        return normalized

    @staticmethod
    def _normalize_symbols(symbols: list[str] | None) -> list[str] | None:
        if symbols is None:
            return None
        normalized = list(dict.fromkeys(
            symbol.strip().upper()
            for symbol in symbols
            if symbol and symbol.strip()
        ))
        if not normalized:
            raise InvalidInputError("At least one valid symbol is required.")
        return normalized

    @staticmethod
    def _validate_limit(limit: int | None) -> None:
        if limit is not None and limit <= 0:
            raise InvalidInputError("Limit must be greater than zero.")

    @staticmethod
    def _validate_interval(interval_seconds: int) -> None:
        if interval_seconds < MIN_INTERVAL_SECONDS:
            raise InvalidInputError(
                f"Interval must be at least {MIN_INTERVAL_SECONDS} seconds."
            )

    @staticmethod
    def _normalize_time(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise InvalidInputError("Schedule times must be timezone-aware.")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _next_run(previous: datetime, interval_seconds: int, now: datetime) -> datetime:
        """Advance beyond now without creating a backlog of missed ticks."""
        candidate = previous + timedelta(seconds=interval_seconds)
        if candidate > now:
            return candidate
        missed = int((now - candidate).total_seconds() // interval_seconds) + 1
        return candidate + timedelta(seconds=missed * interval_seconds)

    @staticmethod
    def _view(schedule: IngestionSchedule) -> IngestionScheduleView:
        return IngestionScheduleView(
            schedule_id=schedule.id,
            name=schedule.name,
            dataset=schedule.dataset,
            symbols=tuple(schedule.symbols) if schedule.symbols is not None else None,
            target_limit=schedule.target_limit,
            only_stale=schedule.only_stale,
            interval_seconds=schedule.interval_seconds,
            next_run_at=schedule.next_run_at,
            enabled=schedule.enabled,
            last_triggered_at=schedule.last_triggered_at,
        )

    @staticmethod
    def _scheduled_idempotency_key(schedule_id: int, scheduled_for: datetime) -> str:
        instant = scheduled_for.astimezone(timezone.utc).isoformat()
        digest = hashlib.sha256(instant.encode("utf-8")).hexdigest()[:32]
        return f"schedule:{schedule_id}:{digest}"

    @staticmethod
    def _job_view(job: IngestionJob) -> IngestionJobView:
        return IngestionJobView(
            job_id=job.id,
            dataset=job.dataset,
            status=job.status,
            idempotency_key=job.idempotency_key,
            attempt_count=job.attempt_count,
            submitted_at=job.submitted_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            worker_id=job.worker_id,
            heartbeat_at=job.heartbeat_at,
            error_summary=job.error_summary,
            last_run_id=None,
        )

    def create(
        self,
        name: str,
        dataset: IngestionDataset,
        *,
        interval_seconds: int,
        next_run_at: datetime | None = None,
        symbols: list[str] | None = None,
        limit: int | None = None,
        only_stale: bool = True,
        enabled: bool = True,
    ) -> IngestionScheduleView:
        if not isinstance(dataset, IngestionDataset):
            raise InvalidInputError("Unsupported ingestion dataset.")
        normalized_name = self._normalize_name(name)
        normalized_symbols = self._normalize_symbols(symbols)
        self._validate_limit(limit)
        self._validate_interval(interval_seconds)
        first_run = self._normalize_time(next_run_at or datetime.now(timezone.utc))

        if self.repository.get_by_name(normalized_name) is not None:
            raise InvalidInputError(
                f"Ingestion schedule '{normalized_name}' already exists."
            )

        try:
            schedule = self.repository.create(
                name=normalized_name,
                dataset=dataset,
                symbols=normalized_symbols,
                target_limit=limit,
                only_stale=only_stale,
                interval_seconds=interval_seconds,
                next_run_at=first_run,
                enabled=enabled,
            )
            self.db.commit()
            return self._view(schedule)
        except IntegrityError:
            self.db.rollback()
            raise InvalidInputError(
                f"Ingestion schedule '{normalized_name}' already exists."
            )

    def get(self, schedule_id: int) -> IngestionScheduleView | None:
        if schedule_id <= 0:
            raise InvalidInputError("Schedule id must be greater than zero.")
        schedule = self.repository.get(schedule_id)
        return None if schedule is None else self._view(schedule)

    def set_enabled(self, schedule_id: int, *, enabled: bool) -> IngestionScheduleView:
        if schedule_id <= 0:
            raise InvalidInputError("Schedule id must be greater than zero.")
        schedule = self.repository.get(schedule_id)
        if schedule is None:
            raise InvalidInputError(f"Ingestion schedule {schedule_id} was not found.")
        now = datetime.now(timezone.utc)
        self.repository.set_enabled(schedule, enabled=enabled, now=now)
        self.db.commit()
        return self._view(schedule)

    def trigger_due(
        self,
        *,
        now: datetime | None = None,
        limit: int = DEFAULT_TRIGGER_BATCH_SIZE,
    ) -> list[ScheduledIngestionTrigger]:
        """Create at most one job per due schedule invocation.

        The schedule and its queued job are committed together. The scheduled
        timestamp is part of the job idempotency key, so a retried scheduler
        invocation cannot create a second job for the same scheduled slot.
        Missed intervals are coalesced rather than replayed as a burst.
        """
        if limit < 1:
            raise InvalidInputError("Trigger limit must be at least one.")
        triggered_at = self._normalize_time(now or datetime.now(timezone.utc))
        schedules = self.repository.get_due(now=triggered_at, limit=limit)
        triggers: list[ScheduledIngestionTrigger] = []

        try:
            for schedule in schedules:
                scheduled_for = self._normalize_time(schedule.next_run_at)
                key = self._scheduled_idempotency_key(schedule.id, scheduled_for)
                existing = self.job_repository.get_job_by_idempotency_key(key)

                if existing is None:
                    symbols = self._normalize_symbols(schedule.symbols)
                    fingerprint = self.orchestrator._request_fingerprint(
                        schedule.dataset,
                        symbols,
                        schedule.target_limit,
                        schedule.only_stale,
                    )
                    job = self.job_repository.create_job(
                        dataset=schedule.dataset,
                        symbols=symbols,
                        limit=schedule.target_limit,
                        only_stale=schedule.only_stale,
                        idempotency_key=key,
                        request_fingerprint=fingerprint,
                    )
                else:
                    job = existing
                    if job.request_fingerprint != self.orchestrator._request_fingerprint(
                        schedule.dataset,
                        self._normalize_symbols(schedule.symbols),
                        schedule.target_limit,
                        schedule.only_stale,
                    ):
                        raise InvalidInputError(
                            "Scheduled idempotency key conflicts with a different ingestion request."
                        )

                next_run = self._next_run(
                    scheduled_for,
                    schedule.interval_seconds,
                    triggered_at,
                )
                self.repository.advance(
                    schedule,
                    triggered_at=triggered_at,
                    next_run_at=next_run,
                )
                triggers.append(
                    ScheduledIngestionTrigger(
                        schedule_id=schedule.id,
                        scheduled_for=scheduled_for,
                        job=self._job_view(job),
                    )
                )

            if schedules:
                self.db.commit()
            return triggers
        except Exception:
            self.db.rollback()
            raise
