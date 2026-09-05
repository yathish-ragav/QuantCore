from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.models.ingestion import IngestionJobStatus
from quantcore.services.ingestion_execution_service import IngestionExecutionService
from quantcore.services.ingestion_orchestrator import IngestionResult


NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)


def make_service():
    db = Mock()
    orchestrator = Mock()
    service = IngestionExecutionService(db, orchestrator=orchestrator)
    service.repository = Mock()
    return service


def make_job(**overrides):
    values = dict(
        id=7,
        dataset=IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL", "MSFT"],
        target_limit=10,
        only_stale=True,
        idempotency_key="job-1",
        request_fingerprint="fingerprint",
        status=IngestionJobStatus.QUEUED,
        attempt_count=0,
        submitted_at=NOW,
        started_at=None,
        finished_at=None,
        worker_id=None,
        heartbeat_at=None,
        error_summary=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_submit_persists_normalized_idempotent_job():
    service = make_service()
    job = make_job()
    service.repository.get_job_by_idempotency_key.return_value = None
    service.repository.create_job.return_value = job
    service.orchestrator._request_fingerprint.return_value = "fingerprint"

    view = service.submit(
        IngestionDataset.PRICE_HISTORY,
        symbols=["aapl", "AAPL", " msft "],
        limit=10,
        idempotency_key="job-1",
    )

    assert view.job_id == 7
    assert view.status is IngestionJobStatus.QUEUED
    service.repository.create_job.assert_called_once_with(
        dataset=IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL", "MSFT"],
        limit=10,
        only_stale=True,
        idempotency_key="job-1",
        request_fingerprint="fingerprint",
    )
    service.db.commit.assert_called_once()


def test_submit_replays_same_idempotency_key():
    service = make_service()
    job = make_job(status=IngestionJobStatus.COMPLETED, attempt_count=1)
    service.repository.get_job_by_idempotency_key.return_value = job
    service.orchestrator._request_fingerprint.return_value = "fingerprint"

    view = service.submit(
        IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL", "MSFT"],
        limit=10,
        idempotency_key="job-1",
    )

    assert view.job_id == 7
    assert view.status is IngestionJobStatus.COMPLETED
    service.repository.create_job.assert_not_called()


def test_submit_rejects_idempotency_key_for_different_request():
    service = make_service()
    service.repository.get_job_by_idempotency_key.return_value = make_job(
        request_fingerprint="different"
    )
    service.orchestrator._request_fingerprint.return_value = "fingerprint"

    with pytest.raises(InvalidInputError, match="different ingestion request"):
        service.submit(
            IngestionDataset.PRICE_HISTORY,
            symbols=["AAPL"],
            idempotency_key="job-1",
        )


def test_claim_is_single_winner():
    service = make_service()
    job = make_job()
    service.repository.get_job.return_value = job
    def claim(job, **kwargs):
        job.status = IngestionJobStatus.RUNNING
        job.attempt_count = 1
        job.worker_id = "worker-a"
        return True

    service.repository.claim_job.side_effect = claim

    view = service.claim(7, worker_id="worker-a")

    assert view.status is IngestionJobStatus.RUNNING
    assert view.attempt_count == 1
    service.repository.claim_job.assert_called_once()
    service.db.commit.assert_called_once()


def test_claim_rejects_already_running_job():
    service = make_service()
    service.repository.get_job.return_value = make_job(
        status=IngestionJobStatus.RUNNING
    )

    with pytest.raises(InvalidInputError, match="not claimable"):
        service.claim(7, worker_id="worker-a")


def test_execute_finishes_job_from_deterministic_orchestrator_result():
    service = make_service()
    queued = make_job()
    running = make_job(status=IngestionJobStatus.RUNNING, attempt_count=1, worker_id="worker-a")
    service.repository.get_job.side_effect = [queued, running, running]
    def claim(job, **kwargs):
        job.status = IngestionJobStatus.RUNNING
        job.attempt_count = 1
        job.worker_id = "worker-a"
        return True
    service.repository.claim_job.side_effect = claim
    service.orchestrator.sync_market.return_value = [
        IngestionResult(
            dataset=IngestionDataset.PRICE_HISTORY,
            eligible=2,
            attempted=2,
            succeeded=1,
            skipped=0,
            failed=1,
            errors=("MSFT: provider unavailable",),
            run_id=12,
        )
    ]

    result = service.execute(7, worker_id="worker-a")

    assert result.run_id == 12
    service.orchestrator.sync_market.assert_called_once_with(
        datasets=[IngestionDataset.PRICE_HISTORY],
        symbols=["AAPL", "MSFT"],
        limit=10,
        only_stale=True,
        idempotency_key=service._run_key(running),
        job_id=7,
        attempt_number=1,
    )
    service.repository.finish_job.assert_called_once()
    assert service.repository.finish_job.call_args.kwargs["status"] is IngestionJobStatus.COMPLETED_WITH_ERRORS


def test_heartbeat_requires_owning_worker():
    service = make_service()
    service.repository.get_job.return_value = make_job(
        status=IngestionJobStatus.RUNNING,
        worker_id="worker-a",
    )

    with pytest.raises(InvalidInputError, match="owning worker"):
        service.heartbeat(7, worker_id="worker-b")


def test_cancel_only_allows_queued_jobs():
    service = make_service()
    service.repository.get_job.return_value = make_job(
        status=IngestionJobStatus.RUNNING
    )

    with pytest.raises(InvalidInputError, match="Only queued"):
        service.cancel(7)


def test_retry_requeues_terminal_partial_job():
    service = make_service()
    job = make_job(status=IngestionJobStatus.COMPLETED_WITH_ERRORS, attempt_count=1)
    service.repository.get_job.return_value = job

    service.repository.requeue_job.side_effect = lambda value: setattr(
        value, "status", IngestionJobStatus.QUEUED
    )

    view = service.retry(7)

    assert view.status is IngestionJobStatus.QUEUED
    service.repository.requeue_job.assert_called_once_with(job)
    service.db.commit.assert_called_once()


def test_recover_stale_jobs_marks_abandoned_work_failed():
    service = make_service()
    job = make_job(
        status=IngestionJobStatus.RUNNING,
        heartbeat_at=NOW - timedelta(hours=2),
    )
    service.repository.get_running_jobs_started_before.return_value = [job]
    service.orchestrator.recover_stale_runs.return_value = 1

    recovered = service.recover_stale(
        stale_after=timedelta(hours=1),
        now=NOW,
    )

    assert recovered == 1
    service.repository.finish_job.assert_called_once()
    assert service.repository.finish_job.call_args.kwargs["status"] is IngestionJobStatus.FAILED
