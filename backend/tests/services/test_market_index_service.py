from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import DataValidationError, InvalidInputError, ResourceNotFoundError
from quantcore.services.market_index_service import IndexConstituentInput, MarketIndexService


def make_index():
    index = Mock()
    index.id = 1
    index.key = "SP500"
    index.name = "S&P 500"
    index.provider = "licensed-provider"
    index.methodology_reference = "methodology-ref"
    index.source_reference = "source-ref"
    index.is_active = True
    return index


def make_existing(start, end=None, security_id=10):
    row = Mock()
    row.security_id = security_id
    row.effective_from = start
    row.effective_to = end
    return row


def make_service():
    service = MarketIndexService.__new__(MarketIndexService)
    service.db = Mock()
    service.repository = Mock()
    return service


def test_create_normalizes_key_and_rejects_duplicate():
    service = make_service()
    service.repository.get_by_key.return_value = None
    service.repository.create.return_value = make_index()

    result = service.create(
        key=" sp500 ",
        name="S&P 500",
        provider="licensed-provider",
    )

    assert result.key == "SP500"
    service.repository.create.assert_called_once_with(
        key="SP500",
        name="S&P 500",
        provider="licensed-provider",
        methodology_reference=None,
        source_reference=None,
    )
    service.db.flush.assert_called_once()


def test_create_rejects_duplicate_index_key():
    service = make_service()
    service.repository.get_by_key.return_value = make_index()

    with pytest.raises(DataValidationError, match="already exists"):
        service.create(key="sp500", name="S&P 500", provider="provider")


def test_add_constituents_rejects_missing_security():
    service = make_service()
    service.repository.get_by_key.return_value = make_index()
    service.db.scalars.return_value.all.return_value = []

    with pytest.raises(ResourceNotFoundError, match="10"):
        service.add_constituents(
            "SP500",
            [IndexConstituentInput(10, date(2020, 1, 1), known_at=__import__('datetime').datetime(2020, 1, 1))],
        )


def test_add_constituents_rejects_overlapping_existing_interval():
    service = make_service()
    service.repository.get_by_key.return_value = make_index()
    service.db.scalars.return_value.all.return_value = [10]
    service.repository.get_constituents_for_security.return_value = [
        make_existing(date(2020, 1, 1), date(2021, 1, 1))
    ]

    with pytest.raises(DataValidationError, match="overlap"):
        service.add_constituents(
            "SP500",
            [IndexConstituentInput(10, date(2020, 6, 1), known_at=__import__('datetime').datetime(2020, 1, 1))],
        )


def test_add_constituents_rejects_overlap_inside_batch():
    service = make_service()
    service.repository.get_by_key.return_value = make_index()
    service.db.scalars.return_value.all.return_value = [10]
    service.repository.get_constituents_for_security.return_value = []

    with pytest.raises(DataValidationError, match="overlap"):
        service.add_constituents(
            "SP500",
            [
                IndexConstituentInput(10, date(2020, 1, 1), date(2021, 1, 1), known_at=__import__('datetime').datetime(2020, 1, 1)),
                IndexConstituentInput(10, date(2020, 6, 1), known_at=__import__('datetime').datetime(2020, 1, 1)),
            ],
        )


def test_add_constituents_persists_non_overlapping_membership():
    service = make_service()
    service.repository.get_by_key.return_value = make_index()
    service.db.scalars.return_value.all.return_value = [10, 11]
    service.repository.get_constituents_for_security.return_value = []

    result = service.add_constituents(
        "SP500",
        [
            IndexConstituentInput(
                10,
                date(2020, 1, 1),
                date(2021, 1, 1),
                Decimal("0.06"),
                "source-a",
                __import__('datetime').datetime(2020, 1, 1),
            ),
            IndexConstituentInput(
                11,
                date(2020, 1, 1),
                None,
                Decimal("0.04"),
                "source-a",
                __import__('datetime').datetime(2020, 1, 1),
            ),
        ],
        observed_at=__import__("datetime").datetime(2026, 1, 1),
    )

    assert result == 2
    assert service.repository.create_constituent.call_count == 2
    calls = service.repository.create_constituent.call_args_list
    assert calls[0].kwargs["known_at"].tzinfo == __import__("datetime").timezone.utc
    assert calls[1].kwargs["known_at"].tzinfo == __import__("datetime").timezone.utc
    service.db.flush.assert_called_once()


def test_add_constituents_rejects_invalid_interval_and_weight():
    service = make_service()
    with pytest.raises(InvalidInputError):
        service._normalize_input(
            IndexConstituentInput(10, date(2021, 1, 1), date(2020, 1, 1))
        )
    with pytest.raises(InvalidInputError):
        service._normalize_input(
            IndexConstituentInput(10, date(2020, 1, 1), weight=Decimal("-1"))
        )


def test_resolve_returns_deterministic_point_in_time_snapshot():
    service = make_service()
    service.repository.get_by_key.return_value = make_index()
    member_a = make_existing(date(2020, 1, 1), None, 11)
    member_b = make_existing(date(2019, 1, 1), None, 10)
    service.repository.get_constituents_as_of.return_value = [member_a, member_b]

    first = service.resolve("sp500", as_of=__import__("datetime").datetime(2020, 6, 1))
    second = service.resolve("SP500", as_of=__import__("datetime").datetime(2020, 6, 1))

    assert first.security_ids == (10, 11)
    assert first.size == 2
    assert first.fingerprint == second.fingerprint
    service.repository.get_constituents_as_of.assert_called_with(1, effective_on=date(2020, 6, 1), known_at=__import__("datetime").datetime(2020, 6, 1, tzinfo=__import__("datetime").timezone.utc))
