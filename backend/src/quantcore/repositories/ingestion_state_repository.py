from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.models.ingestion import (
    IngestionJob,
    IngestionJobStatus,
    IngestionRun,
    IngestionRunStatus,
    IngestionState,
)


class IngestionStateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(
        self,
        dataset: IngestionDataset,
        *,
        company_id: int | None = None,
        security_id: int | None = None,
    ) -> IngestionState | None:
        stmt = select(IngestionState).where(
            IngestionState.dataset == dataset,
        )

        if company_id is not None:
            stmt = stmt.where(IngestionState.company_id == company_id)

        if security_id is not None:
            stmt = stmt.where(IngestionState.security_id == security_id)

        return self.db.scalar(stmt)

    def get_or_create(
        self,
        dataset: IngestionDataset,
        scope: IngestionScope,
        *,
        company_id: int | None = None,
        security_id: int | None = None,
    ) -> IngestionState:
        state = self.get(
            dataset,
            company_id=company_id,
            security_id=security_id,
        )
        if state is not None:
            return state

        state = IngestionState(
            dataset=dataset,
            scope=scope,
            company_id=company_id,
            security_id=security_id,
        )
        self.db.add(state)
        self.db.flush()
        return state

    def mark_attempt(
        self,
        state: IngestionState,
        attempted_at: datetime,
    ) -> None:
        state.last_attempt_at = attempted_at

    def mark_success(
        self,
        state: IngestionState,
        *,
        succeeded_at: datetime,
        source: str | None,
        records: int,
    ) -> None:
        state.last_success_at = succeeded_at
        state.last_success_source = source
        state.last_success_records = records
        state.consecutive_failures = 0
        state.last_error = None
        state.updated_at = succeeded_at

    def mark_failure(
        self,
        state: IngestionState,
        *,
        failed_at: datetime,
        error: str,
    ) -> None:
        state.consecutive_failures += 1
        state.last_error = error[:2000]
        state.updated_at = failed_at

    def get_run_by_idempotency_key(
        self,
        dataset: IngestionDataset,
        idempotency_key: str,
    ) -> IngestionRun | None:
        stmt = select(IngestionRun).where(
            IngestionRun.dataset == dataset,
            IngestionRun.idempotency_key == idempotency_key,
        )
        return self.db.scalar(stmt)

    def create_run(
        self,
        dataset: IngestionDataset | None,
        *,
        idempotency_key: str | None = None,
        request_fingerprint: str | None = None,
        job_id: int | None = None,
        attempt_number: int = 1,
    ) -> IngestionRun:
        run = IngestionRun(
            dataset=dataset,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            job_id=job_id,
            attempt_number=attempt_number,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def create_job(
        self,
        *,
        dataset: IngestionDataset,
        symbols: list[str] | None,
        limit: int | None,
        only_stale: bool,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> IngestionJob:
        job = IngestionJob(
            dataset=dataset,
            symbols=symbols,
            target_limit=limit,
            only_stale=only_stale,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get_job(self, job_id: int) -> IngestionJob | None:
        return self.db.get(IngestionJob, job_id)

    def get_job_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> IngestionJob | None:
        return self.db.scalar(
            select(IngestionJob).where(
                IngestionJob.idempotency_key == idempotency_key
            )
        )

    def get_queued_jobs(self, *, limit: int = 1) -> list[IngestionJob]:
        if limit < 1:
            raise ValueError("limit must be at least one")
        stmt = (
            select(IngestionJob)
            .where(IngestionJob.status == IngestionJobStatus.QUEUED)
            .order_by(IngestionJob.submitted_at, IngestionJob.id)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def claim_job(
        self,
        job: IngestionJob,
        *,
        worker_id: str,
        started_at: datetime,
    ) -> bool:
        result = self.db.execute(
            update(IngestionJob)
            .where(
                IngestionJob.id == job.id,
                IngestionJob.status == IngestionJobStatus.QUEUED,
            )
            .values(
                status=IngestionJobStatus.RUNNING,
                attempt_count=IngestionJob.attempt_count + 1,
                started_at=started_at,
                finished_at=None,
                worker_id=worker_id,
                heartbeat_at=started_at,
                error_summary=None,
            )
        )
        if result.rowcount != 1:
            return False
        self.db.refresh(job)
        return True

    def heartbeat_job(self, job: IngestionJob, *, at: datetime) -> None:
        job.heartbeat_at = at

    def finish_job(
        self,
        job: IngestionJob,
        *,
        status: IngestionJobStatus,
        finished_at: datetime,
        error_summary: str | None = None,
    ) -> None:
        job.status = status
        job.finished_at = finished_at
        job.heartbeat_at = finished_at
        job.error_summary = error_summary[:4000] if error_summary else None

    def requeue_job(self, job: IngestionJob) -> None:
        job.status = IngestionJobStatus.QUEUED
        job.started_at = None
        job.finished_at = None
        job.worker_id = None
        job.heartbeat_at = None
        job.error_summary = None

    def get_running_jobs_started_before(
        self,
        cutoff: datetime,
    ) -> list[IngestionJob]:
        stmt = (
            select(IngestionJob)
            .where(
                IngestionJob.status == IngestionJobStatus.RUNNING,
                IngestionJob.heartbeat_at < cutoff,
            )
            .order_by(IngestionJob.heartbeat_at, IngestionJob.id)
        )
        return list(self.db.scalars(stmt).all())

    def get_running_runs_started_before(
        self,
        cutoff: datetime,
    ) -> list[IngestionRun]:
        """Return RUNNING executions older than the supplied cutoff."""
        stmt = (
            select(IngestionRun)
            .where(
                IngestionRun.status == IngestionRunStatus.RUNNING,
                IngestionRun.started_at < cutoff,
            )
            .order_by(IngestionRun.started_at, IngestionRun.id)
        )
        return list(self.db.scalars(stmt).all())

    def get_run(self, run_id: int) -> IngestionRun | None:
        return self.db.get(IngestionRun, run_id)

    def finish_run(
        self,
        run: IngestionRun,
        *,
        status: IngestionRunStatus,
        finished_at: datetime,
        attempted: int,
        succeeded: int,
        skipped: int,
        failed: int,
        eligible: int = 0,
        error_summary: str | None = None,
    ) -> None:
        run.status = status
        run.finished_at = finished_at
        run.attempted = attempted
        run.succeeded = succeeded
        run.skipped = skipped
        run.failed = failed
        run.eligible = eligible
        run.error_summary = error_summary[:4000] if error_summary else None
