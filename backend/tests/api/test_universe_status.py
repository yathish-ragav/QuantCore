from datetime import datetime, timezone
from unittest.mock import Mock

from quantcore.api.endpoints.universe import get_universe_status
from quantcore.models.universe_sync import UniverseSyncRun, UniverseSyncRunStatus


def test_universe_status_maps_latest_run_and_coverage():
    run = UniverseSyncRun(
        source="SEC",
        status=UniverseSyncRunStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        records_processed=10,
        active_companies=8,
        active_securities=10,
        inactive_securities=2,
    )
    run.id = 1

    service = Mock()
    service.get_status.return_value = (
        run,
        {
            "active_companies": 8,
            "active_securities": 10,
            "inactive_securities": 2,
        },
    )

    response = get_universe_status(service)

    assert response.latest_run.id == 1
    assert response.latest_run.status == "COMPLETED"
    assert response.coverage.active_securities == 10
