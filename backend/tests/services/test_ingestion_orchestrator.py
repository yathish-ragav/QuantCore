from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import (
    DATASET_POLICIES,
    DATASET_SCOPES,
    IngestionDataset,
    IngestionScope,
)
from quantcore.models.ingestion import IngestionRunStatus
from quantcore.models.security import SecurityStatus
from quantcore.services.ingestion_orchestrator import (
    IngestionOrchestrator,
)
from quantcore.services.sec_filing_service import SECFilingSyncResult
from quantcore.services.sec_xbrl_fact_service import SECXBRLFactSyncResult


def make_security(
    security_id=10,
    company_id=1,
    symbol="AAPL",
):
    security = Mock()
    security.id = security_id
    security.company_id = company_id
    security.symbol = symbol
    security.status = SecurityStatus.ACTIVE
    return security


def make_state(
    dataset,
    *,
    company_id=None,
    security_id=None,
    last_success_at=None,
):
    state = Mock()
    state.dataset = dataset
    state.company_id = company_id
    state.security_id = security_id
    state.last_attempt_at = last_success_at
    state.last_success_at = last_success_at
    state.last_success_source = "FMP"
    state.last_success_records = 1
    state.consecutive_failures = 0
    state.last_error = None
    return state


def make_service():
    service = IngestionOrchestrator.__new__(IngestionOrchestrator)
    service.db = Mock()
    service.state_repo = Mock()
    return service


def test_freshness_requires_successful_ingestion():
    service = make_service()
    now = datetime.now(timezone.utc)

    assert service._is_fresh(
        None,
        IngestionDataset.BALANCE_SHEET,
        now,
    ) is False

    state = make_state(
        IngestionDataset.BALANCE_SHEET,
        last_success_at=now - timedelta(
            seconds=DATASET_POLICIES[
                IngestionDataset.BALANCE_SHEET
            ].max_age.total_seconds() + 1
        ),
    )

    assert service._is_fresh(
        state,
        IngestionDataset.BALANCE_SHEET,
        now,
    ) is False


def test_freshness_is_true_inside_policy_window():
    service = make_service()
    now = datetime.now(timezone.utc)

    state = make_state(
        IngestionDataset.NEWS,
        last_success_at=now - timedelta(minutes=30),
    )

    assert service._is_fresh(
        state,
        IngestionDataset.NEWS,
        now,
    ) is True


def test_get_freshness_reports_all_registered_datasets():
    service = make_service()
    security = make_security()

    service.db.scalars.return_value.all.return_value = [security]
    service.state_repo.get.return_value = None

    result = service.get_freshness("aapl")

    assert len(result) == len(IngestionDataset)
    assert {
        view.dataset
        for view in result
    } == set(IngestionDataset)
    assert all(view.is_fresh is False for view in result)


def test_get_freshness_unknown_symbol_returns_empty():
    service = make_service()
    service.db.scalars.return_value.all.return_value = []

    assert service.get_freshness("UNKNOWN") == []


def test_sync_market_deduplicates_company_scoped_work():
    service = make_service()
    security_a = make_security(10, 1, "AAPL")
    security_b = make_security(11, 1, "AAPL-P")
    service.db.scalars.return_value.all.return_value = [
        security_a,
        security_b,
    ]

    run = Mock()
    run.id = 1
    service.state_repo.create_run.return_value = run
    service.state_repo.get.return_value = None
    service.state_repo.get_or_create.return_value = Mock()

    dataset = IngestionDataset.BALANCE_SHEET
    fake_dataset_service = Mock()
    fake_dataset_service.provider.SOURCE = "FMP"
    fake_dataset_service.sync_balance_sheets.return_value = [
        Mock()
    ]

    original = service._service_for
    service._service_for = Mock(return_value=fake_dataset_service)

    result = service.sync_market(
        datasets=[dataset],
        only_stale=False,
    )

    assert result[0].attempted == 1
    assert result[0].succeeded == 1
    fake_dataset_service.sync_balance_sheets.assert_called_once_with("AAPL")
    service.state_repo.finish_run.assert_called_once()

    service._service_for = original


def test_sync_market_skips_fresh_state():
    service = make_service()
    security = make_security()
    service.db.scalars.return_value.all.return_value = [security]

    run = Mock()
    run.id = 1
    service.state_repo.create_run.return_value = run

    fresh = make_state(
        IngestionDataset.PRICE_HISTORY,
        security_id=security.id,
        last_success_at=datetime.now(timezone.utc),
    )
    service.state_repo.get.return_value = fresh

    service._service_for = Mock()

    result = service.sync_market(
        datasets=[IngestionDataset.PRICE_HISTORY],
        only_stale=True,
    )

    assert result[0].attempted == 0
    assert result[0].skipped == 1
    service._service_for.assert_not_called()


def test_sync_market_records_failure_without_stopping_other_symbols():
    service = make_service()
    first = make_security(10, 1, "AAPL")
    second = make_security(11, 2, "MSFT")
    service.db.scalars.return_value.all.return_value = [
        first,
        second,
    ]

    run = Mock()
    run.id = 1
    service.state_repo.create_run.return_value = run
    service.state_repo.get.return_value = None
    service.state_repo.get_or_create.return_value = Mock()

    fake_service = Mock()
    fake_service.provider.SOURCE = "FMP"
    fake_service.sync_balance_sheets.side_effect = [
        RuntimeError("provider unavailable"),
        [Mock()],
    ]
    service._service_for = Mock(return_value=fake_service)

    result = service.sync_market(
        datasets=[IngestionDataset.BALANCE_SHEET],
        only_stale=False,
    )

    assert result[0].attempted == 2
    assert result[0].succeeded == 1
    assert result[0].failed == 1
    assert len(result[0].errors) == 1
    service.state_repo.mark_failure.assert_called_once()
    service.state_repo.finish_run.assert_called_once()


def test_sync_market_supports_sec_filing_dataset():
    service = make_service()
    security = make_security()
    service.db.scalars.return_value.all.return_value = [security]

    run = Mock()
    run.id = 1
    service.state_repo.create_run.return_value = run
    service.state_repo.get.return_value = None
    service.state_repo.get_or_create.return_value = Mock()

    fake_service = Mock()
    fake_service.provider.SOURCE = "SEC"
    fake_service.sync_filings.return_value = SECFilingSyncResult(
        created=2,
        updated=1,
        unchanged=4,
        events_created=1,
        records_processed=7,
    )
    service._service_for = Mock(return_value=fake_service)

    result = service.sync_market(
        datasets=[IngestionDataset.SEC_FILINGS],
        only_stale=False,
    )

    assert result[0].dataset is IngestionDataset.SEC_FILINGS
    assert result[0].attempted == 1
    assert result[0].succeeded == 1
    fake_service.sync_filings.assert_called_once_with("AAPL")


def test_sync_market_supports_corporate_actions_dataset():
    service = make_service()
    security = make_security()
    service.db.scalars.return_value.all.return_value = [security]

    run = Mock()
    run.id = 1
    service.state_repo.create_run.return_value = run
    service.state_repo.get.return_value = None
    service.state_repo.get_or_create.return_value = Mock()

    fake_service = Mock()
    fake_service.client.SOURCE = "YAHOO"
    fake_service.sync_corporate_actions.return_value = Mock(
        records_processed=3
    )
    service._service_for = Mock(return_value=fake_service)

    result = service.sync_market(
        datasets=[IngestionDataset.CORPORATE_ACTIONS],
        only_stale=False,
    )

    assert result[0].dataset is IngestionDataset.CORPORATE_ACTIONS
    assert result[0].attempted == 1
    assert result[0].succeeded == 1
    fake_service.sync_corporate_actions.assert_called_once_with("AAPL")


def test_sync_market_supports_sec_xbrl_fact_dataset():
    service = make_service()
    security = make_security()
    service.db.scalars.return_value.all.return_value = [security]

    run = Mock()
    run.id = 1
    service.state_repo.create_run.return_value = run
    service.state_repo.get.return_value = None
    service.state_repo.get_or_create.return_value = Mock()

    fake_service = Mock()
    fake_service.provider.SOURCE = "SEC"
    fake_service.sync_facts.return_value = SECXBRLFactSyncResult(
        created=5,
        unchanged=2,
        records_processed=7,
    )
    service._service_for = Mock(return_value=fake_service)

    result = service.sync_market(
        datasets=[IngestionDataset.SEC_XBRL_FACTS],
        only_stale=False,
    )

    assert result[0].dataset is IngestionDataset.SEC_XBRL_FACTS
    assert result[0].attempted == 1
    assert result[0].succeeded == 1
    fake_service.sync_facts.assert_called_once_with("AAPL")


def test_idempotency_fingerprint_is_deterministic():
    service = make_service()

    first = service._request_fingerprint(
        IngestionDataset.PRICE_HISTORY,
        ["AAPL", "MSFT"],
        10,
        True,
    )
    second = service._request_fingerprint(
        IngestionDataset.PRICE_HISTORY,
        ["AAPL", "MSFT"],
        10,
        True,
    )

    assert first == second
    assert len(first) == 64


def test_idempotency_replays_completed_run_without_creating_work():
    service = make_service()
    run = Mock()
    run.id = 7
    run.status = IngestionRunStatus.COMPLETED
    run.request_fingerprint = "fingerprint"
    run.attempted = 2
    run.succeeded = 2
    run.skipped = 0
    run.failed = 0
    run.error_summary = None
    service.state_repo.get_run_by_idempotency_key.return_value = run

    result_run, replayed = service._get_or_create_run(
        IngestionDataset.PRICE_HISTORY,
        idempotency_key="run-123",
        request_fingerprint="fingerprint",
    )

    assert result_run is run
    assert replayed is True
    service.state_repo.create_run.assert_not_called()


def test_idempotency_rejects_different_request_fingerprint():
    service = make_service()
    run = Mock()
    run.status = IngestionRunStatus.COMPLETED
    run.request_fingerprint = "original"
    service.state_repo.get_run_by_idempotency_key.return_value = run

    with pytest.raises(InvalidInputError, match="different ingestion request"):
        service._get_or_create_run(
            IngestionDataset.PRICE_HISTORY,
            idempotency_key="run-123",
            request_fingerprint="different",
        )


def test_idempotency_rejects_existing_running_run():
    service = make_service()
    run = Mock()
    run.status = IngestionRunStatus.RUNNING
    run.request_fingerprint = "fingerprint"
    service.state_repo.get_run_by_idempotency_key.return_value = run

    with pytest.raises(InvalidInputError, match="already running"):
        service._get_or_create_run(
            IngestionDataset.PRICE_HISTORY,
            idempotency_key="run-123",
            request_fingerprint="fingerprint",
        )


def test_idempotency_key_is_validated_before_execution():
    service = make_service()

    with pytest.raises(InvalidInputError, match="must not be empty"):
        service.sync_market(
            datasets=[IngestionDataset.PRICE_HISTORY],
            idempotency_key="   ",
        )

    with pytest.raises(InvalidInputError, match="at most 128 characters"):
        service.sync_market(
            datasets=[IngestionDataset.PRICE_HISTORY],
            idempotency_key="x" * 129,
        )


def test_result_from_completed_run_preserves_counts_and_errors():
    service = make_service()
    run = Mock()
    run.attempted = 3
    run.succeeded = 2
    run.skipped = 0
    run.failed = 1
    run.error_summary = "AAPL: provider unavailable; MSFT: timeout"

    result = service._result_from_run(
        IngestionDataset.NEWS,
        run,
    )

    assert result.dataset is IngestionDataset.NEWS
    assert result.attempted == 3
    assert result.succeeded == 2
    assert result.failed == 1
    assert result.errors == (
        "AAPL: provider unavailable",
        "MSFT: timeout",
    )
