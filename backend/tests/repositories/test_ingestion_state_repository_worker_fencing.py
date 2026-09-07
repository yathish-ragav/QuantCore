from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from quantcore.models.ingestion import IngestionJob, IngestionJobStatus
from quantcore.db.database import Base
from quantcore.repositories.ingestion_state_repository import IngestionStateRepository
from quantcore.ingestion.datasets import IngestionDataset


NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)


def _job(db: Session, *, status=IngestionJobStatus.QUEUED, attempt_count=0, heartbeat_at=None):
    job = IngestionJob(
        dataset=IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL"],
        target_limit=1,
        only_stale=True,
        idempotency_key=f"job-{id(db)}-{attempt_count}-{status.value}",
        request_fingerprint="f" * 64,
        status=status,
        attempt_count=attempt_count,
        submitted_at=NOW,
        started_at=NOW if status is IngestionJobStatus.RUNNING else None,
        heartbeat_at=heartbeat_at,
        worker_id="worker-a" if status is IngestionJobStatus.RUNNING else None,
    )
    db.add(job)
    db.flush()
    return job


def _engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[IngestionJob.__table__])
    return engine


def test_claim_has_single_winner_and_increments_attempt():
    engine = _engine()
    with Session(engine) as db_a, Session(engine) as db_b:
        job_a = _job(db_a)
        db_a.commit()
        job_b = db_b.get(IngestionJob, job_a.id)

        repo_a = IngestionStateRepository(db_a)
        repo_b = IngestionStateRepository(db_b)

        assert repo_a.claim_job(job_a, worker_id="worker-a", started_at=NOW) is True
        assert repo_b.claim_job(job_b, worker_id="worker-b", started_at=NOW) is False
        db_a.commit()
        db_b.rollback()

        current = db_a.get(IngestionJob, job_a.id)
        assert current.status is IngestionJobStatus.RUNNING
        assert current.attempt_count == 1
        assert current.worker_id == "worker-a"
    engine.dispose()


def test_heartbeat_and_completion_are_fenced_by_attempt():
    engine = _engine()
    with Session(engine) as db:
        job = _job(
            db,
            status=IngestionJobStatus.RUNNING,
            attempt_count=2,
            heartbeat_at=NOW,
        )
        db.commit()
        repo = IngestionStateRepository(db)

        assert repo.heartbeat_job(
            job, worker_id="worker-a", attempt_number=1, at=NOW + timedelta(minutes=1)
        ) is False
        assert repo.heartbeat_job(
            job, worker_id="worker-a", attempt_number=2, at=NOW + timedelta(minutes=1)
        ) is True
        assert repo.finish_owned_job(
            job,
            worker_id="worker-a",
            status=IngestionJobStatus.COMPLETED,
            finished_at=NOW + timedelta(minutes=2),
            attempt_number=1,
        ) is False
        assert repo.finish_owned_job(
            job,
            worker_id="worker-a",
            status=IngestionJobStatus.COMPLETED,
            finished_at=NOW + timedelta(minutes=2),
            attempt_number=2,
        ) is True
        db.commit()
    engine.dispose()


def test_stale_recovery_cannot_overwrite_fresh_heartbeat():
    engine = _engine()
    with Session(engine) as db_a, Session(engine) as db_b:
        job_a = _job(
            db_a,
            status=IngestionJobStatus.RUNNING,
            attempt_count=1,
            heartbeat_at=NOW,
        )
        db_a.commit()
        job_b = db_b.get(IngestionJob, job_a.id)
        repo_b = IngestionStateRepository(db_b)
        assert repo_b.heartbeat_job(
            job_b, worker_id="worker-a", attempt_number=1, at=NOW + timedelta(minutes=3, seconds=59)
        ) is True
        db_b.commit()

        stale_candidate = db_a.get(IngestionJob, job_a.id)
        repo_a = IngestionStateRepository(db_a)
        assert repo_a.recover_stale_job(
            stale_candidate,
            cutoff=NOW + timedelta(minutes=3),
            recovered_at=NOW + timedelta(minutes=4),
        ) is False
        db_a.rollback()

        current = db_a.get(IngestionJob, job_a.id)
        assert current.status is IngestionJobStatus.RUNNING
        assert current.worker_id == "worker-a"
    engine.dispose()
