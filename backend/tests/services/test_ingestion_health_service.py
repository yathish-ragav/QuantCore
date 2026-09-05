from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.services.ingestion_health_service import (
    IngestionHealthService,
    IngestionHealthStatus,
)
from quantcore.services.ingestion_orchestrator import FreshnessView


NOW = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


def freshness(
    dataset=IngestionDataset.PRICE_HISTORY,
    *,
    fresh=True,
    last_success_at=NOW,
    last_attempt_at=NOW,
    consecutive_failures=0,
):
    return FreshnessView(
        dataset=dataset,
        scope=IngestionScope.SECURITY,
        last_attempt_at=last_attempt_at,
        last_success_at=last_success_at,
        last_success_source="FMP",
        last_success_records=10,
        consecutive_failures=consecutive_failures,
        last_error="provider unavailable" if consecutive_failures else None,
        is_fresh=fresh,
    )


def test_health_classification_is_deterministic():
    service = IngestionHealthService.__new__(IngestionHealthService)

    assert service._status(freshness()) is IngestionHealthStatus.HEALTHY
    assert service._status(freshness()) is IngestionHealthStatus.HEALTHY


def test_never_ingested_is_distinct_from_failed():
    service = IngestionHealthService.__new__(IngestionHealthService)

    assert (
        service._status(
            freshness(last_success_at=None, last_attempt_at=None)
        )
        is IngestionHealthStatus.NEVER_INGESTED
    )
    assert (
        service._status(
            freshness(
                last_success_at=None,
                last_attempt_at=NOW,
                consecutive_failures=2,
            )
        )
        is IngestionHealthStatus.FAILED
    )


def test_stale_success_is_stale():
    service = IngestionHealthService.__new__(IngestionHealthService)

    assert (
        service._status(
            freshness(
                fresh=False,
                last_success_at=NOW - timedelta(days=10),
                last_attempt_at=NOW - timedelta(days=10),
            )
        )
        is IngestionHealthStatus.STALE
    )


def test_failed_attempt_after_success_is_failed():
    service = IngestionHealthService.__new__(IngestionHealthService)

    assert (
        service._status(
            freshness(
                fresh=False,
                last_success_at=NOW - timedelta(days=2),
                last_attempt_at=NOW,
                consecutive_failures=1,
            )
        )
        is IngestionHealthStatus.FAILED
    )


def test_success_with_no_outstanding_failure_can_be_healthy():
    service = IngestionHealthService.__new__(IngestionHealthService)

    assert (
        service._status(
            freshness(
                fresh=True,
                last_success_at=NOW,
                last_attempt_at=NOW,
                consecutive_failures=0,
            )
        )
        is IngestionHealthStatus.HEALTHY
    )


def test_assess_normalizes_symbol_and_delegates():
    service = IngestionHealthService.__new__(IngestionHealthService)
    service._orchestrator = Mock()
    service._orchestrator.get_freshness.return_value = [freshness()]

    result = service.assess(" aapl ")

    service._orchestrator.get_freshness.assert_called_once_with("AAPL")
    assert len(result) == 1
    assert result[0].status is IngestionHealthStatus.HEALTHY


def test_assess_rejects_empty_symbol():
    service = IngestionHealthService.__new__(IngestionHealthService)
    service._orchestrator = Mock()

    with pytest.raises(InvalidInputError, match="Symbol must not be empty"):
        service.assess("   ")

    service._orchestrator.get_freshness.assert_not_called()


def test_overall_status_returns_worst_status():
    service = IngestionHealthService.__new__(IngestionHealthService)
    views = tuple(
        service._view(item)
        for item in (
            freshness(fresh=True),
            freshness(
                dataset=IngestionDataset.NEWS,
                fresh=False,
                last_success_at=NOW - timedelta(days=1),
                last_attempt_at=NOW - timedelta(days=1),
            ),
            freshness(
                dataset=IngestionDataset.BALANCE_SHEET,
                last_success_at=None,
                last_attempt_at=NOW,
                consecutive_failures=1,
            ),
        )
    )

    assert service.overall_status(views) is IngestionHealthStatus.FAILED


def test_overall_status_for_empty_views_is_never_ingested():
    service = IngestionHealthService.__new__(IngestionHealthService)

    assert service.overall_status(()) is IngestionHealthStatus.NEVER_INGESTED
