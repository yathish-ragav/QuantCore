from unittest.mock import Mock

from quantcore.services.universe_sync_service import UniverseSyncService


def test_sync_records_completed_run_without_changing_universe_sync_transaction_contract():
    db = Mock()
    service = UniverseSyncService.__new__(UniverseSyncService)
    service.db = db
    service.repository = Mock()
    service.universe_service = Mock()

    run = Mock(error=None)
    service.repository.create_run.return_value = run
    service.repository.get_counts.return_value = (10, 12, 2)
    service.universe_service.sync.return_value = 12

    result = service.sync()

    assert result == 12
    service.repository.create_run.assert_called_once()
    service.universe_service.sync.assert_called_once_with()
    assert run.status == "COMPLETED"
    assert run.records_processed == 12
    assert run.active_companies == 10
    assert run.active_securities == 12
    assert run.inactive_securities == 2
    assert run.error is None
    assert db.commit.call_count == 2
    db.rollback.assert_not_called()


def test_sync_marks_persisted_run_failed_after_universe_sync_error():
    db = Mock()
    service = UniverseSyncService.__new__(UniverseSyncService)
    service.db = db
    service.repository = Mock()
    service.universe_service = Mock()

    run = Mock()
    failed_run = Mock()
    service.repository.create_run.return_value = run
    service.repository.get_latest.return_value = failed_run
    service.universe_service.sync.side_effect = RuntimeError("provider failed")

    try:
        service.sync()
    except RuntimeError as exc:
        assert str(exc) == "provider failed"
    else:
        raise AssertionError("RuntimeError was not raised")

    assert failed_run.status == "FAILED"
    assert failed_run.error == "provider failed"
    db.rollback.assert_called_once()
    assert db.commit.call_count == 2
