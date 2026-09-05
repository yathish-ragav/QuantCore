from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.models.ingestion import (
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
    ) -> IngestionRun:
        run = IngestionRun(
            dataset=dataset,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        self.db.add(run)
        self.db.flush()
        return run

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
        error_summary: str | None = None,
    ) -> None:
        run.status = status
        run.finished_at = finished_at
        run.attempted = attempted
        run.succeeded = succeeded
        run.skipped = skipped
        run.failed = failed
        run.error_summary = error_summary[:4000] if error_summary else None
