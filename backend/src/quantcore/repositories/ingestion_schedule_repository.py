from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.ingestion_schedule import IngestionSchedule


class IngestionScheduleRepository:
    """Persistence operations for durable ingestion schedules."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, schedule_id: int) -> IngestionSchedule | None:
        return self.db.get(IngestionSchedule, schedule_id)

    def get_by_name(self, name: str) -> IngestionSchedule | None:
        return self.db.scalar(
            select(IngestionSchedule).where(IngestionSchedule.name == name)
        )

    def create(
        self,
        *,
        name: str,
        dataset,
        symbols: list[str] | None,
        target_limit: int | None,
        only_stale: bool,
        interval_seconds: int,
        next_run_at: datetime,
        enabled: bool,
    ) -> IngestionSchedule:
        schedule = IngestionSchedule(
            name=name,
            dataset=dataset,
            symbols=symbols,
            target_limit=target_limit,
            only_stale=only_stale,
            interval_seconds=interval_seconds,
            next_run_at=next_run_at,
            enabled=enabled,
        )
        self.db.add(schedule)
        self.db.flush()
        return schedule

    def get_due(self, *, now: datetime, limit: int) -> list[IngestionSchedule]:
        if limit < 1:
            raise ValueError("limit must be at least one")
        stmt = (
            select(IngestionSchedule)
            .where(
                IngestionSchedule.enabled.is_(True),
                IngestionSchedule.next_run_at <= now,
            )
            .order_by(IngestionSchedule.next_run_at, IngestionSchedule.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(self.db.scalars(stmt).all())

    def advance(
        self,
        schedule: IngestionSchedule,
        *,
        triggered_at: datetime,
        next_run_at: datetime,
    ) -> None:
        schedule.last_triggered_at = triggered_at
        schedule.next_run_at = next_run_at
        schedule.updated_at = triggered_at

    def set_enabled(
        self,
        schedule: IngestionSchedule,
        *,
        enabled: bool,
        now: datetime,
    ) -> None:
        schedule.enabled = enabled
        schedule.updated_at = now
