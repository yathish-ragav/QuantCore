from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from quantcore.models.research_experiment import (
    ResearchExperimentArtifact,
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

    def get_by_run_ids(self, run_ids: tuple[str, ...]) -> list[ResearchExperimentRun]:
        if not run_ids:
            return []
        return list(
            self.db.scalars(
                select(ResearchExperimentRun)
                .where(ResearchExperimentRun.run_id.in_(run_ids))
                .order_by(
                    ResearchExperimentRun.submitted_at.desc(),
                    ResearchExperimentRun.id.desc(),
                )
            ).all()
        )

    def list_runs(
        self,
        *,
        experiment_key: str | None = None,
        definition_version: str | None = None,
        statuses: tuple[ResearchExperimentRunStatus, ...] | None = None,
        submitted_after: datetime | None = None,
        submitted_before: datetime | None = None,
        limit: int = 100,
    ) -> list[ResearchExperimentRun]:
        if limit < 1:
            raise ValueError("limit must be at least one")

        stmt = select(ResearchExperimentRun)
        if experiment_key is not None:
            stmt = stmt.where(
                ResearchExperimentRun.experiment_key == experiment_key
            )
        if definition_version is not None:
            stmt = stmt.where(
                ResearchExperimentRun.definition_version == definition_version
            )
        if statuses:
            stmt = stmt.where(ResearchExperimentRun.status.in_(statuses))
        if submitted_after is not None:
            stmt = stmt.where(ResearchExperimentRun.submitted_at >= submitted_after)
        if submitted_before is not None:
            stmt = stmt.where(ResearchExperimentRun.submitted_at <= submitted_before)

        stmt = (
            stmt.order_by(
                ResearchExperimentRun.submitted_at.desc(),
                ResearchExperimentRun.id.desc(),
            )
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

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


    def get_artifact(self, artifact_id: str) -> ResearchExperimentArtifact | None:
        return self.db.scalar(
            select(ResearchExperimentArtifact).where(
                ResearchExperimentArtifact.artifact_id == artifact_id
            )
        )

    def list_artifacts(self, run_id: str) -> list[ResearchExperimentArtifact]:
        return list(
            self.db.scalars(
                select(ResearchExperimentArtifact)
                .where(ResearchExperimentArtifact.run_id == run_id)
                .order_by(ResearchExperimentArtifact.created_at, ResearchExperimentArtifact.id)
            )
        )

    def get_artifact_by_fingerprint(
        self, run_id: str, artifact_fingerprint: str
    ) -> ResearchExperimentArtifact | None:
        return self.db.scalar(
            select(ResearchExperimentArtifact).where(
                ResearchExperimentArtifact.run_id == run_id,
                ResearchExperimentArtifact.artifact_fingerprint == artifact_fingerprint,
            )
        )

    def create_artifact(
        self,
        *,
        artifact_id: str,
        run_id: str,
        artifact_type: str,
        content_hash: str,
        artifact_fingerprint: str,
        metadata: dict,
        provenance: dict,
        created_at: datetime,
    ) -> ResearchExperimentArtifact:
        artifact = ResearchExperimentArtifact(
            artifact_id=artifact_id,
            run_id=run_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            artifact_fingerprint=artifact_fingerprint,
            artifact_metadata=metadata,
            provenance=provenance,
            created_at=created_at,
        )
        self.db.add(artifact)
        self.db.flush()
        return artifact
