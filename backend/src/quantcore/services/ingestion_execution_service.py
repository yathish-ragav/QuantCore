from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.models.ingestion import (
    IngestionJob,
    IngestionJobStatus,
)
from quantcore.repositories.ingestion_state_repository import IngestionStateRepository
from quantcore.services.ingestion_orchestrator import (
    IngestionOrchestrator,
    IngestionResult,
)


@dataclass(frozen=True)
class IngestionJobView:
    """Stable read model for the persistent operational ingestion boundary."""

    job_id: int
    dataset: IngestionDataset
    status: IngestionJobStatus
    idempotency_key: str
    attempt_count: int
    submitted_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    worker_id: str | None
    heartbeat_at: datetime | None
    error_summary: str | None
    last_run_id: int | None


class IngestionExecutionService:
    """Own the persistent job lifecycle around the synchronous ingestion core.

    This service deliberately does not introduce a queue, scheduler, or worker
    framework. It provides the durable contract those components will consume:
    submit -> claim -> execute -> finish, with recovery and retryable jobs.
    """

    def __init__(self, db: Session, *, orchestrator: IngestionOrchestrator | None = None):
        self.db = db
        self.repository = IngestionStateRepository(db)
        self.orchestrator = orchestrator or IngestionOrchestrator(db)

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
    def _validate_key(idempotency_key: str) -> str:
        key = idempotency_key.strip()
        if not key:
            raise InvalidInputError("Idempotency key must not be empty.")
        if len(key) > 128:
            raise InvalidInputError("Idempotency key must be at most 128 characters.")
        return key

    @staticmethod
    def _run_key(job: IngestionJob) -> str:
        raw = f"{job.idempotency_key}:attempt:{job.attempt_count}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _view(job: IngestionJob, last_run_id: int | None = None) -> IngestionJobView:
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
            last_run_id=last_run_id,
        )

    def submit(
        self,
        dataset: IngestionDataset,
        *,
        symbols: list[str] | None = None,
        limit: int | None = None,
        only_stale: bool = True,
        idempotency_key: str | None = None,
    ) -> IngestionJobView:
        """Persist a new queued job, or return the existing idempotent job."""
        if not isinstance(dataset, IngestionDataset):
            raise InvalidInputError("Unsupported ingestion dataset.")
        normalized_symbols = self._normalize_symbols(symbols)
        self._validate_limit(limit)

        key = self._validate_key(idempotency_key) if idempotency_key else uuid4().hex
        fingerprint = self.orchestrator._request_fingerprint(
            dataset, normalized_symbols, limit, only_stale
        )

        existing = self.repository.get_job_by_idempotency_key(key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise InvalidInputError(
                    "Idempotency key was already used for a different ingestion request."
                )
            return self._view(existing)

        try:
            job = self.repository.create_job(
                dataset=dataset,
                symbols=normalized_symbols,
                limit=limit,
                only_stale=only_stale,
                idempotency_key=key,
                request_fingerprint=fingerprint,
            )
            self.db.commit()
            return self._view(job)
        except IntegrityError:
            self.db.rollback()
            existing = self.repository.get_job_by_idempotency_key(key)
            if existing is None:
                raise
            if existing.request_fingerprint != fingerprint:
                raise InvalidInputError(
                    "Idempotency key was already used for a different ingestion request."
                )
            return self._view(existing)

    def get(self, job_id: int) -> IngestionJobView | None:
        if job_id <= 0:
            raise InvalidInputError("Job id must be greater than zero.")
        job = self.repository.get_job(job_id)
        return None if job is None else self._view(job)

    def claim(self, job_id: int, *, worker_id: str) -> IngestionJobView:
        """Atomically claim a queued job for one operational worker."""
        if job_id <= 0:
            raise InvalidInputError("Job id must be greater than zero.")
        worker_id = worker_id.strip()
        if not worker_id or len(worker_id) > 128:
            raise InvalidInputError("Worker id must be 1-128 characters.")

        job = self.repository.get_job(job_id)
        if job is None:
            raise InvalidInputError(f"Ingestion job {job_id} was not found.")
        if job.status is not IngestionJobStatus.QUEUED:
            raise InvalidInputError(
                f"Ingestion job {job_id} is not claimable from {job.status.value}."
            )

        now = datetime.now(timezone.utc)
        if not self.repository.claim_job(job, worker_id=worker_id, started_at=now):
            raise InvalidInputError(f"Ingestion job {job_id} was claimed by another worker.")

        self.db.commit()
        return self._view(job)

    def execute(self, job_id: int, *, worker_id: str) -> IngestionResult:
        """Claim and execute one job through the existing deterministic core."""
        claimed = self.claim(job_id, worker_id=worker_id)
        job = self.repository.get_job(job_id)
        if job is None:
            raise InvalidInputError(f"Ingestion job {job_id} disappeared after claim.")

        try:
            self.repository.heartbeat_job(job, at=datetime.now(timezone.utc))
            self.db.commit()

            results = self.orchestrator.sync_market(
                datasets=[job.dataset],
                symbols=job.symbols,
                limit=job.target_limit,
                only_stale=job.only_stale,
                idempotency_key=self._run_key(job),
                job_id=job.id,
                attempt_number=job.attempt_count,
            )
            if len(results) != 1:
                raise RuntimeError("Ingestion execution returned an invalid result count.")

            result = results[0]
            status = (
                IngestionJobStatus.COMPLETED_WITH_ERRORS
                if result.failed > 0
                else IngestionJobStatus.COMPLETED
            )
            job = self.repository.get_job(job_id)
            if job is not None:
                self.repository.finish_job(
                    job,
                    status=status,
                    finished_at=datetime.now(timezone.utc),
                    error_summary="; ".join(result.errors) if result.errors else None,
                )
                self.db.commit()
            return result
        except Exception as exc:
            self.db.rollback()
            job = self.repository.get_job(job_id)
            if job is not None and job.status is IngestionJobStatus.RUNNING:
                self.repository.finish_job(
                    job,
                    status=IngestionJobStatus.FAILED,
                    finished_at=datetime.now(timezone.utc),
                    error_summary=str(exc),
                )
                self.db.commit()
            raise

    def execute_next(self, *, worker_id: str) -> IngestionResult | None:
        """Claim the oldest queued job; return None when the queue is empty."""
        jobs = self.repository.get_queued_jobs(limit=1)
        if not jobs:
            return None
        try:
            return self.execute(jobs[0].id, worker_id=worker_id)
        except InvalidInputError as exc:
            if "claimed by another worker" in str(exc):
                return None
            raise

    def heartbeat(self, job_id: int, *, worker_id: str) -> IngestionJobView:
        if job_id <= 0:
            raise InvalidInputError("Job id must be greater than zero.")
        worker_id = worker_id.strip()
        job = self.repository.get_job(job_id)
        if job is None:
            raise InvalidInputError(f"Ingestion job {job_id} was not found.")
        if job.status is not IngestionJobStatus.RUNNING or job.worker_id != worker_id:
            raise InvalidInputError("Only the owning worker may heartbeat a running job.")
        self.repository.heartbeat_job(job, at=datetime.now(timezone.utc))
        self.db.commit()
        return self._view(job)

    def cancel(self, job_id: int) -> IngestionJobView:
        """Cancel queued work only; running provider calls are never interrupted."""
        if job_id <= 0:
            raise InvalidInputError("Job id must be greater than zero.")
        job = self.repository.get_job(job_id)
        if job is None:
            raise InvalidInputError(f"Ingestion job {job_id} was not found.")
        if job.status is not IngestionJobStatus.QUEUED:
            raise InvalidInputError("Only queued ingestion jobs can be cancelled.")
        self.repository.finish_job(
            job,
            status=IngestionJobStatus.CANCELLED,
            finished_at=datetime.now(timezone.utc),
        )
        self.db.commit()
        return self._view(job)

    def retry(self, job_id: int) -> IngestionJobView:
        """Requeue a terminal failed/partial job as a new execution attempt."""
        if job_id <= 0:
            raise InvalidInputError("Job id must be greater than zero.")
        job = self.repository.get_job(job_id)
        if job is None:
            raise InvalidInputError(f"Ingestion job {job_id} was not found.")
        if job.status not in (
            IngestionJobStatus.FAILED,
            IngestionJobStatus.COMPLETED_WITH_ERRORS,
        ):
            raise InvalidInputError(
                "Only failed or partially completed jobs can be retried."
            )
        self.repository.requeue_job(job)
        self.db.commit()
        return self._view(job)

    def recover_stale(
        self,
        *,
        stale_after: timedelta,
        now: datetime | None = None,
    ) -> int:
        """Recover abandoned jobs and their associated coordinator runs."""
        if stale_after.total_seconds() <= 0:
            raise InvalidInputError("stale_after must be greater than zero.")
        recovered_at = now or datetime.now(timezone.utc)
        cutoff = recovered_at - stale_after
        recovered_runs = self.orchestrator.recover_stale_runs(
            stale_after=stale_after,
            now=recovered_at,
        )
        jobs = self.repository.get_running_jobs_started_before(cutoff)
        for job in jobs:
            self.repository.finish_job(
                job,
                status=IngestionJobStatus.FAILED,
                finished_at=recovered_at,
                error_summary="Ingestion job became stale before completion.",
            )
        if jobs:
            self.db.commit()
        return max(recovered_runs, len(jobs))
