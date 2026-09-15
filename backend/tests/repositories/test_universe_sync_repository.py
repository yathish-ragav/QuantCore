from datetime import datetime, timezone
from unittest.mock import Mock

from quantcore.repositories.universe_sync_repository import UniverseSyncRepository


def test_create_run_adds_running_record():
    db = Mock()
    repo = UniverseSyncRepository(db)

    started_at = datetime.now(timezone.utc)
    run = repo.create_run("SEC", started_at)

    assert run.source == "SEC"
    assert run.status.value == "RUNNING"
    assert run.started_at == started_at
    db.add.assert_called_once_with(run)
