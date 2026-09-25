from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.services import ingestion_bootstrap as module


def test_bootstrap_creates_declared_schedule(monkeypatch):
    service = Mock()
    service.repository.get_by_name.return_value = None
    service.create.return_value = Mock()
    db = Mock()
    monkeypatch.setattr(module, "SessionLocal", Mock(return_value=db))
    monkeypatch.setattr(module, "IngestionScheduleService", Mock(return_value=service))

    created = module.bootstrap_schedules(
        raw='[{"name":"daily-prices","dataset":"price_history","interval_seconds":86400}]'
    )

    assert created == 1
    service.create.assert_called_once()
    kwargs = service.create.call_args.kwargs
    assert kwargs["dataset"] is IngestionDataset.PRICE_HISTORY
    assert kwargs["interval_seconds"] == 86400
    db.close.assert_called_once()


def test_bootstrap_is_idempotent_for_matching_existing_schedule(monkeypatch):
    service = Mock()
    existing = Mock(
        dataset=IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL", "MSFT"],
        target_limit=100,
        only_stale=True,
        interval_seconds=86400,
        enabled=True,
    )
    service.repository.get_by_name.return_value = existing
    service._normalize_name.side_effect = lambda value: value.strip()
    service._normalize_symbols.side_effect = lambda value: None if value is None else list(dict.fromkeys(value))
    db = Mock()
    monkeypatch.setattr(module, "SessionLocal", Mock(return_value=db))
    monkeypatch.setattr(module, "IngestionScheduleService", Mock(return_value=service))

    created = module.bootstrap_schedules(
        raw='[{"name":"daily-prices","dataset":"price_history","interval_seconds":86400,"symbols":["AAPL","MSFT"],"limit":100}]'
    )

    assert created == 0
    service.create.assert_not_called()
    db.close.assert_called_once()


def test_bootstrap_rejects_configuration_drift(monkeypatch):
    service = Mock()
    existing = Mock(
        dataset=IngestionDataset.PRICE_HISTORY,
        symbols=["AAPL"],
        target_limit=None,
        only_stale=True,
        interval_seconds=86400,
        enabled=True,
    )
    service.repository.get_by_name.return_value = existing
    service._normalize_name.side_effect = lambda value: value.strip()
    service._normalize_symbols.side_effect = lambda value: None if value is None else list(dict.fromkeys(value))
    db = Mock()
    monkeypatch.setattr(module, "SessionLocal", Mock(return_value=db))
    monkeypatch.setattr(module, "IngestionScheduleService", Mock(return_value=service))

    with pytest.raises(InvalidInputError, match="different configuration"):
        module.bootstrap_schedules(
            raw='[{"name":"daily-prices","dataset":"price_history","interval_seconds":3600}]'
        )

    db.close.assert_called_once()
