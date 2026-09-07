from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.ingestion_scheduler import (
    IngestionScheduler,
    IngestionSchedulerConfig,
)

NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)


def test_scheduler_config_rejects_invalid_values():
    with pytest.raises(InvalidInputError):
        IngestionSchedulerConfig(poll_interval_seconds=0)
    with pytest.raises(InvalidInputError):
        IngestionSchedulerConfig(trigger_batch_size=0)


def test_scheduler_stop_sets_shutdown_signal():
    scheduler = IngestionScheduler(session_factory=Mock())
    assert not scheduler._stop_event.is_set()
    scheduler.stop()
    assert scheduler._stop_event.is_set()


def test_scheduler_run_once_triggers_due_schedules_and_closes_session():
    db = Mock()
    factory = Mock(return_value=db)
    service = Mock()
    service.trigger_due.return_value = [
        SimpleNamespace(
            schedule_id=5,
            job=SimpleNamespace(job_id=42),
        ),
        SimpleNamespace(
            schedule_id=6,
            job=SimpleNamespace(job_id=43),
        ),
    ]

    import quantcore.services.ingestion_scheduler as module

    original = module.IngestionScheduleService
    module.IngestionScheduleService = Mock(return_value=service)
    try:
        scheduler = IngestionScheduler(
            session_factory=factory,
            config=IngestionSchedulerConfig(
                poll_interval_seconds=10,
                trigger_batch_size=25,
            ),
        )

        assert scheduler.run_once() == 2
        service.trigger_due.assert_called_once()
        kwargs = service.trigger_due.call_args.kwargs
        assert kwargs["limit"] == 25
        assert kwargs["now"].tzinfo is not None
        db.close.assert_called_once()
    finally:
        module.IngestionScheduleService = original


def test_scheduler_run_once_returns_zero_when_nothing_is_due():
    db = Mock()
    factory = Mock(return_value=db)
    service = Mock()
    service.trigger_due.return_value = []

    import quantcore.services.ingestion_scheduler as module

    original = module.IngestionScheduleService
    module.IngestionScheduleService = Mock(return_value=service)
    try:
        scheduler = IngestionScheduler(session_factory=factory)
        assert scheduler.run_once() == 0
        db.close.assert_called_once()
    finally:
        module.IngestionScheduleService = original


def test_scheduler_run_forever_stops_without_claiming_work_after_stop():
    scheduler = IngestionScheduler(session_factory=Mock())
    scheduler.stop()
    scheduler.run_once = Mock()

    scheduler.run_forever()

    scheduler.run_once.assert_not_called()
