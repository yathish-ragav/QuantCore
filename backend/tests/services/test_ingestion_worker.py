from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.ingestion_orchestrator import IngestionResult
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.services.ingestion_worker import (
    IngestionWorker,
    IngestionWorkerConfig,
)


def test_worker_config_rejects_invalid_intervals():
    with pytest.raises(InvalidInputError):
        IngestionWorkerConfig(poll_interval_seconds=0)
    with pytest.raises(InvalidInputError):
        IngestionWorkerConfig(heartbeat_interval_seconds=0)
    with pytest.raises(InvalidInputError):
        IngestionWorkerConfig(
            heartbeat_interval_seconds=30,
            stale_after_seconds=30,
        )


def test_worker_stop_sets_shutdown_signal():
    worker = IngestionWorker(session_factory=Mock(), worker_id="worker-a")
    assert not worker._stop_event.is_set()
    worker.stop()
    assert worker._stop_event.is_set()


def test_worker_recovery_uses_configured_stale_threshold():
    db = Mock()
    factory = Mock(return_value=db)
    service = Mock()
    service.recover_stale.return_value = 2

    # Patch the service constructor at the module boundary so the worker's
    # session lifecycle remains under test.
    import quantcore.services.ingestion_worker as module
    original = module.IngestionExecutionService
    module.IngestionExecutionService = Mock(return_value=service)
    try:
        worker = IngestionWorker(
            session_factory=factory,
            config=IngestionWorkerConfig(stale_after_seconds=120),
        )
        assert worker.recover_stale() == 2
        service.recover_stale.assert_called_once_with(
            stale_after=timedelta(seconds=120)
        )
        db.close.assert_called_once()
    finally:
        module.IngestionExecutionService = original


def test_worker_claims_then_executes_with_same_worker_id():
    db = Mock()
    factory = Mock(return_value=db)
    service = Mock()
    queued = Mock(id=41)
    service.repository.get_queued_jobs.return_value = [queued]
    service.claim.return_value = SimpleNamespace(job_id=41, attempt_count=1)

    import quantcore.services.ingestion_worker as module
    original = module.IngestionExecutionService
    module.IngestionExecutionService = Mock(return_value=service)
    try:
        worker = IngestionWorker(
            session_factory=factory,
            worker_id="worker-a",
        )
        worker._execute_with_heartbeat = Mock()

        assert worker.run_once() is True
        service.claim.assert_called_once_with(41, worker_id="worker-a")
        worker._execute_with_heartbeat.assert_called_once_with(41, 1)
        db.close.assert_called_once()
    finally:
        module.IngestionExecutionService = original


def test_worker_survives_transient_recovery_failure():
    worker = IngestionWorker(
        session_factory=Mock(),
        worker_id="worker-a",
        config=IngestionWorkerConfig(
            poll_interval_seconds=1,
            recovery_interval_seconds=30,
        ),
    )
    worker.recover_stale = Mock(side_effect=RuntimeError("database unavailable"))

    def stop_after_poll():
        worker.stop()
        return False

    worker.run_once = Mock(side_effect=stop_after_poll)

    worker.run_forever()

    worker.recover_stale.assert_called_once()
    worker.run_once.assert_called_once()


def test_worker_logs_completed_job_metrics(caplog):
    db = Mock()
    factory = Mock(return_value=db)
    service = Mock()
    service.execute_claimed.return_value = IngestionResult(
        dataset=IngestionDataset.PRICE_HISTORY,
        eligible=100,
        attempted=80,
        succeeded=75,
        skipped=20,
        failed=5,
        errors=("MSFT: provider unavailable",),
        run_id=123,
    )

    class FakeThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

        def join(self, **_kwargs):
            pass

    import quantcore.services.ingestion_worker as module
    original_service = module.IngestionExecutionService
    original_thread = module.threading.Thread
    module.IngestionExecutionService = Mock(return_value=service)
    module.threading.Thread = FakeThread
    try:
        worker = IngestionWorker(
            session_factory=factory,
            worker_id="worker-a",
        )
        with caplog.at_level("INFO", logger=module.logger.name):
            worker._execute_with_heartbeat(41, 2)
    finally:
        module.IngestionExecutionService = original_service
        module.threading.Thread = original_thread

    message = " ".join(record.getMessage() for record in caplog.records)
    assert "Ingestion job completed job_id=41" in message
    assert "worker_id=worker-a" in message
    assert "attempt=2" in message
    assert "dataset=price_history" in message
    assert "run_id=123" in message
    assert "eligible=100" in message
    assert "succeeded=75" in message
    assert "failed=5" in message
    assert "duration_ms=" in message
