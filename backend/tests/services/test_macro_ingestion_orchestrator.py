from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from quantcore.ingestion.macro_datasets import MACRO_SERIES_POLICIES
from quantcore.services.macro_ingestion_orchestrator import MacroIngestionOrchestrator
from quantcore.services.macro_service import MacroSyncResult
from quantcore.core.exceptions import InvalidInputError


def make_service():
    service = MacroIngestionOrchestrator.__new__(MacroIngestionOrchestrator)
    service.db = Mock()
    service.state_repo = Mock()
    return service


def make_state(last_success_at=None):
    state = Mock()
    state.last_success_at = last_success_at
    state.last_success_vintage = datetime(2026, 8, 27, tzinfo=timezone.utc).date()
    state.last_success_records = 5
    state.consecutive_failures = 0
    state.last_error = None
    return state


def test_freshness_requires_successful_ingestion():
    service = make_service()
    now = datetime.now(timezone.utc)
    policy = MACRO_SERIES_POLICIES["GDP"]

    assert service._is_fresh(None, policy, now) is False
    assert service._is_fresh(
        make_state(now - policy.max_age - timedelta(seconds=1)), policy, now
    ) is False


def test_freshness_is_true_inside_policy_window():
    service = make_service()
    now = datetime.now(timezone.utc)
    policy = MACRO_SERIES_POLICIES["GDP"]

    assert service._is_fresh(
        make_state(now - timedelta(minutes=30)), policy, now
    ) is True


def test_sync_series_skips_fresh_series_without_provider_call():
    service = make_service()
    state = make_state(datetime.now(timezone.utc))
    service.state_repo.get.return_value = state

    with patch(
        "quantcore.services.macro_ingestion_orchestrator.MacroService"
    ) as macro_service:
        result = service.sync_series("gdp", only_stale=True)

    assert result.skipped is True
    macro_service.assert_not_called()


def test_sync_series_records_success():
    service = make_service()
    service.state_repo.get.return_value = None
    state = make_state()
    service.state_repo.get_or_create.return_value = state

    with patch(
        "quantcore.services.macro_ingestion_orchestrator.MacroService"
    ) as macro_service_class:
        macro_service_class.return_value.sync_series.return_value = MacroSyncResult(
            created=4,
            unchanged=1,
            records_processed=5,
            vintage_date=datetime(2026, 8, 27, tzinfo=timezone.utc).date(),
        )
        result = service.sync_series("gdp", only_stale=False)

    assert result.succeeded is True
    assert result.records_processed == 5
    service.state_repo.mark_success.assert_called_once()
    service.db.commit.assert_called()


def test_sync_managed_rejects_invalid_limit():
    service = make_service()
    with pytest.raises(InvalidInputError):
        service.sync_managed(limit=0)
