from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from quantcore.models.research_experiment import (
    ResearchExperimentRun,
    ResearchExperimentRunResult,
    ResearchExperimentRunStatus,
)


class ResearchExperimentRepository:
    """Persistence operations for experiment run identity and lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, run_id: str) -> ResearchExperimentRun | None:
        return self.db.scalar(
            select(ResearchExperimentRun).where(
                ResearchExperimentRun.run_id == run_id
            )
        )

    def create(
        self,
        *,
        run_id: str,
        experiment_key: str,
        definition_version: str,
        run_input_fingerprint: str,
        definition_payload: dict,
        submitted_at: datetime,
    ) -> ResearchExperimentRun:
        run = ResearchExperimentRun(
            run_id=run_id,
            experiment_key=experiment_key,
            definition_version=definition_version,
            run_input_fingerprint=run_input_fingerprint,
            definition_payload=definition_payload,
            status=ResearchExperimentRunStatus.QUEUED,
            submitted_at=submitted_at,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def transition(
        self,
        run: ResearchExperimentRun,
        *,
        expected_statuses: tuple[ResearchExperimentRunStatus, ...],
        status: ResearchExperimentRunStatus,
        now: datetime,
        error_summary: str | None = None,
    ) -> bool:
        values = {"status": status}
        if status is ResearchExperimentRunStatus.RUNNING:
            values.update(started_at=now, finished_at=None, error_summary=None)
        elif status in (
            ResearchExperimentRunStatus.COMPLETED,
            ResearchExperimentRunStatus.FAILED,
            ResearchExperimentRunStatus.CANCELLED,
        ):
            values.update(
                finished_at=now,
                error_summary=error_summary[:4000] if error_summary else None,
            )

        result = self.db.execute(
            update(ResearchExperimentRun)
            .where(
                ResearchExperimentRun.id == run.id,
                ResearchExperimentRun.status.in_(expected_statuses),
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return False
        self.db.refresh(run)
        return True


    def get_result(self, run_id: str) -> ResearchExperimentRunResult | None:
        return self.db.scalar(
            select(ResearchExperimentRunResult).where(
                ResearchExperimentRunResult.run_id == run_id
            )
        )

    def create_result(
        self,
        *,
        run_id: str,
        result_payload: dict,
        metrics: dict,
        result_fingerprint: str,
        recorded_at: datetime,
    ) -> ResearchExperimentRunResult:
        result = ResearchExperimentRunResult(
            run_id=run_id,
            result_payload=result_payload,
            metrics=metrics,
            result_fingerprint=result_fingerprint,
            recorded_at=recorded_at,
        )
        self.db.add(result)
        self.db.flush()
        return result
