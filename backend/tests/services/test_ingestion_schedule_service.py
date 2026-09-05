from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.models.ingestion import IngestionJobStatus
from quantcore.services.ingestion_schedule_service import (
    IngestionScheduleService,
)

NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)


def make_schedule(**overrides):
    values = dict(
        id=5,
        name="daily-prices",
        dataset=IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL", "MSFT"],
        target_limit=100,
        only_stale=True,
        interval_seconds=86400,
        next_run_at=NOW,
        enabled=True,
        last_triggered_at=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def make_job(**overrides):
    values = dict(
        id=42,
        dataset=IngestionDataset.PRICE_HISTORY,
        status=IngestionJobStatus.QUEUED,
        idempotency_key="schedule:5:key",
        request_fingerprint="fingerprint",
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


def make_service():
    db = Mock()
    service = IngestionScheduleService(db, orchestrator=Mock())
    service.repository = Mock()
    service.job_repository = Mock()
    return service


def test_create_normalizes_and_persists_schedule():
    service = make_service()
    schedule = make_schedule(symbols=["AAPL", "MSFT"])
    service.repository.get_by_name.return_value = None
    service.repository.create.return_value = schedule

    view = service.create(
        " daily-prices ",
        IngestionDataset.PRICE_HISTORY,
        interval_seconds=86400,
        next_run_at=NOW,
        symbols=["aapl", "AAPL", " msft "],
        limit=100,
    )

    assert view.schedule_id == 5
    assert view.symbols == ("AAPL", "MSFT")
    service.repository.create.assert_called_once_with(
        name="daily-prices",
        dataset=IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL", "MSFT"],
        target_limit=100,
        only_stale=True,
        interval_seconds=86400,
        next_run_at=NOW,
        enabled=True,
    )
    service.db.commit.assert_called_once()


def test_create_rejects_short_interval():
    service = make_service()
    with pytest.raises(InvalidInputError, match="at least 60 seconds"):
        service.create("too-fast", IngestionDataset.PRICE_HISTORY, interval_seconds=59)


def test_create_rejects_duplicate_name():
    service = make_service()
    service.repository.get_by_name.return_value = make_schedule()
    with pytest.raises(InvalidInputError, match="already exists"):
        service.create("daily-prices", IngestionDataset.PRICE_HISTORY, interval_seconds=86400)


def test_trigger_due_creates_job_and_advances_schedule():
    service = make_service()
    schedule = make_schedule()
    job = make_job()
    service.repository.get_due.return_value = [schedule]
    service.job_repository.get_job_by_idempotency_key.return_value = None
    service.job_repository.create_job.return_value = job
    service.orchestrator._request_fingerprint.return_value = "fingerprint"

    triggers = service.trigger_due(now=NOW + timedelta(minutes=5))

    assert len(triggers) == 1
    assert triggers[0].schedule_id == 5
    assert triggers[0].scheduled_for == NOW
    assert triggers[0].job.job_id == 42
    service.job_repository.create_job.assert_called_once_with(
        dataset=IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL", "MSFT"],
        limit=100,
        only_stale=True,
        idempotency_key=service._scheduled_idempotency_key(5, NOW),
        request_fingerprint="fingerprint",
    )
    service.repository.advance.assert_called_once()
    assert service.db.commit.call_count == 1


def test_trigger_due_reuses_existing_idempotent_job():
    service = make_service()
    schedule = make_schedule()
    job = make_job()
    service.repository.get_due.return_value = [schedule]
    service.job_repository.get_job_by_idempotency_key.return_value = job
    service.orchestrator._request_fingerprint.return_value = "fingerprint"

    triggers = service.trigger_due(now=NOW)

    assert triggers[0].job.job_id == 42
    service.job_repository.create_job.assert_not_called()
    service.repository.advance.assert_called_once()


def test_trigger_due_coalesces_missed_intervals():
    service = make_service()
    schedule = make_schedule(interval_seconds=3600)
    job = make_job()
    service.repository.get_due.return_value = [schedule]
    service.job_repository.get_job_by_idempotency_key.return_value = None
    service.job_repository.create_job.return_value = job
    service.orchestrator._request_fingerprint.return_value = "fingerprint"

    service.trigger_due(now=NOW + timedelta(hours=5, minutes=10))

    next_run = service.repository.advance.call_args.kwargs["next_run_at"]
    assert next_run == NOW + timedelta(hours=6)


def test_trigger_due_rejects_conflicting_existing_job():
    service = make_service()
    schedule = make_schedule()
    job = make_job(request_fingerprint="different")
    service.repository.get_due.return_value = [schedule]
    service.job_repository.get_job_by_idempotency_key.return_value = job
    service.orchestrator._request_fingerprint.return_value = "fingerprint"

    with pytest.raises(InvalidInputError, match="conflicts"):
        service.trigger_due(now=NOW)

    service.db.rollback.assert_called_once()
    service.repository.advance.assert_not_called()


def test_trigger_due_does_not_run_ingestion_worker():
    service = make_service()
    service.repository.get_due.return_value = []

    assert service.trigger_due(now=NOW) == []
    service.orchestrator.sync_market.assert_not_called()
    service.db.commit.assert_not_called()


def test_set_enabled_changes_persistent_schedule():
    service = make_service()
    schedule = make_schedule()
    service.repository.get.return_value = schedule
    def set_enabled(schedule, *, enabled, now):
        schedule.enabled = enabled
    service.repository.set_enabled.side_effect = set_enabled

    view = service.set_enabled(5, enabled=False)

    assert view.enabled is False
    service.repository.set_enabled.assert_called_once()
    service.db.commit.assert_called_once()


def test_trigger_due_validates_limit():
    service = make_service()
    with pytest.raises(InvalidInputError, match="at least one"):
        service.trigger_due(now=NOW, limit=0)
