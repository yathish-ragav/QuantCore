from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.models.provenance import DataSource
from quantcore.services.ingestion_lineage_service import IngestionLineageService


AS_OF = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


def make_service():
    service = IngestionLineageService.__new__(IngestionLineageService)
    service.repository = Mock()
    return service


def test_record_success_normalizes_source_and_persists_lineage():
    service = make_service()
    expected = Mock()
    service.repository.record_success.return_value = expected

    result = service.record_success(
        ingestion_run_id=7,
        dataset=IngestionDataset.PRICE_HISTORY,
        scope=IngestionScope.SECURITY,
        security_id=42,
        source="YAHOO",
        records_processed=250,
        recorded_at=AS_OF,
    )

    assert result is expected
    kwargs = service.repository.record_success.call_args.kwargs
    assert kwargs["ingestion_run_id"] == 7
    assert kwargs["dataset"] is IngestionDataset.PRICE_HISTORY
    assert kwargs["scope"] is IngestionScope.SECURITY
    assert kwargs["security_id"] == 42
    assert kwargs["company_id"] is None
    assert kwargs["source"] is DataSource.YAHOO
    assert kwargs["records_processed"] == 250
    assert kwargs["recorded_at"] == AS_OF


def test_record_success_rejects_invalid_entity_scope():
    service = make_service()

    with pytest.raises(InvalidInputError, match="Security-scoped"):
        service.record_success(
            ingestion_run_id=7,
            dataset=IngestionDataset.PRICE_HISTORY,
            scope=IngestionScope.SECURITY,
            company_id=1,
            records_processed=1,
        )


def test_record_success_rejects_unknown_source():
    service = make_service()

    with pytest.raises(InvalidInputError, match="Unsupported ingestion lineage source"):
        service.record_success(
            ingestion_run_id=7,
            dataset=IngestionDataset.PRICE_HISTORY,
            scope=IngestionScope.SECURITY,
            security_id=42,
            source="UNKNOWN",
            records_processed=1,
        )


def test_record_success_rejects_negative_records():
    service = make_service()

    with pytest.raises(InvalidInputError, match="must not be negative"):
        service.record_success(
            ingestion_run_id=7,
            dataset=IngestionDataset.PRICE_HISTORY,
            scope=IngestionScope.SECURITY,
            security_id=42,
            records_processed=-1,
        )


def test_for_run_returns_immutable_sequence():
    service = make_service()
    first = Mock()
    second = Mock()
    service.repository.list_for_run.return_value = [first, second]

    result = service.for_run(7)

    assert result == (first, second)
    service.repository.list_for_run.assert_called_once_with(7)


def test_for_run_rejects_invalid_id():
    service = make_service()

    with pytest.raises(InvalidInputError, match="greater than zero"):
        service.for_run(0)


def test_for_entity_requires_matching_scope_identity():
    service = make_service()

    with pytest.raises(InvalidInputError, match="Company lineage requires"):
        service.for_entity(
            IngestionDataset.BALANCE_SHEET,
            IngestionScope.COMPANY,
            security_id=42,
        )
