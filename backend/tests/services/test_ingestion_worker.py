from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
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
