from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.enums import FinancialStatementType
from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.pit_alignment_service import (
    PITAlignedSnapshot,
    PITAlignmentService,
)


def make_service():
    service = PITAlignmentService.__new__(PITAlignmentService)
    service.db = Mock()
    service.security_repo = Mock()
    service.price_revision_repo = Mock()
    service.financial_revision_repo = Mock()
    service.corporate_action_revision_repo = Mock()
    service.sec_fact_repo = Mock()
    service.macro_repo = Mock()

    # Collection-returning repository methods must default to
    # empty collections rather than an unconfigured Mock.
    service.price_revision_repo.get_latest_for_security_as_of.return_value = []
    service.financial_revision_repo.get_latest_for_company_as_of.return_value = []
    service.corporate_action_revision_repo.get_latest_for_security_as_of.return_value = []
    service.sec_fact_repo.get_latest_for_company_as_of_timestamp.return_value = []

    return service


def make_security():
    security = Mock()
    security.id = 10
    security.symbol = "AAPL"
    security.company_id = 20
    security.company = Mock(id=20)
    return security


def test_get_snapshot_uses_one_shared_timestamp_for_all_pit_sources():
    service = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()

    service.price_revision_repo.get_latest_for_security_as_of.return_value = [
        "price"
    ]

    service.financial_revision_repo.get_latest_for_company_as_of.side_effect = [
        ["income"],
        ["balance"],
        ["cashflow"],
    ]

    service.corporate_action_revision_repo.get_latest_for_security_as_of.return_value = [
        "action"
    ]

    service.sec_fact_repo.get_latest_for_company_as_of_timestamp.return_value = [
        "fact"
    ]

    series = Mock(id=7)
    service.macro_repo.get_series.return_value = series
    service.macro_repo.get_latest_as_of.return_value = ["macro"]

    as_of = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)

    result = service.get_snapshot(
        " aapl ",
        as_of=as_of,
        macro_series_ids=["gdp"],
    )

    assert isinstance(result, PITAlignedSnapshot)
    assert result.symbol == "AAPL"
    assert result.security_id == 10
    assert result.company_id == 20
    assert result.as_of == as_of

    assert result.prices == ("price",)
    assert result.income_statements == ("income",)
    assert result.balance_sheets == ("balance",)
    assert result.cash_flow_statements == ("cashflow",)
    assert result.corporate_actions == ("action",)
    assert result.sec_xbrl_facts == ("fact",)
    assert result.macro_observations == {"GDP": ("macro",)}

    service.price_revision_repo.get_latest_for_security_as_of.assert_called_once_with(
        10,
        as_of,
    )

    assert (
        service.financial_revision_repo.get_latest_for_company_as_of.call_args_list
        == [
            ((20, FinancialStatementType.INCOME, as_of),),
            ((20, FinancialStatementType.BALANCE_SHEET, as_of),),
            ((20, FinancialStatementType.CASH_FLOW, as_of),),
        ]
    )

    service.corporate_action_revision_repo.get_latest_for_security_as_of.assert_called_once_with(
        10,
        as_of,
    )

    service.sec_fact_repo.get_latest_for_company_as_of_timestamp.assert_called_once_with(
        20,
        as_of,
    )

    service.macro_repo.get_latest_as_of.assert_called_once_with(
        7,
        as_of.date(),
    )


def test_get_snapshot_rejects_future_timestamp():
    service = make_service()

    future = datetime(
        2999,
        1,
        1,
        tzinfo=timezone.utc,
    )

    with pytest.raises(InvalidInputError):
        service.get_snapshot(
            "AAPL",
            as_of=future,
        )

    service.security_repo.get_by_symbol.assert_not_called()


def test_get_snapshot_requires_existing_security():
    service = make_service()
    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(ResourceNotFoundError):
        service.get_snapshot(
            "AAPL",
            as_of=datetime(
                2026,
                8,
                20,
                tzinfo=timezone.utc,
            ),
        )


def test_get_snapshot_interprets_naive_as_of_as_utc():
    service = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()

    as_of = datetime(
        2026,
        8,
        20,
        15,
        30,
    )

    result = service.get_snapshot(
        "AAPL",
        as_of=as_of,
    )

    expected_as_of = datetime(
        2026,
        8,
        20,
        15,
        30,
        tzinfo=timezone.utc,
    )

    assert result.as_of == expected_as_of

    service.price_revision_repo.get_latest_for_security_as_of.assert_called_once_with(
        10,
        expected_as_of,
    )

    service.sec_fact_repo.get_latest_for_company_as_of_timestamp.assert_called_once_with(
        20,
        expected_as_of,
    )


def test_get_snapshot_rejects_blank_macro_series_id():
    service = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()

    with pytest.raises(InvalidInputError):
        service.get_snapshot(
            "AAPL",
            as_of=datetime(
                2026,
                8,
                20,
                tzinfo=timezone.utc,
            ),
            macro_series_ids=[""],
        )

    service.macro_repo.get_series.assert_not_called()


def test_get_snapshot_rejects_missing_macro_series():
    service = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()
    service.macro_repo.get_series.return_value = None

    with pytest.raises(ResourceNotFoundError):
        service.get_snapshot(
            "AAPL",
            as_of=datetime(
                2026,
                8,
                20,
                tzinfo=timezone.utc,
            ),
            macro_series_ids=["GDP"],
        )

    service.macro_repo.get_latest_as_of.assert_not_called()


def test_get_snapshot_without_macro_series_returns_empty_mapping():
    service = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()

    result = service.get_snapshot(
        "AAPL",
        as_of=datetime(
            2026,
            8,
            20,
            tzinfo=timezone.utc,
        ),
    )

    assert result.macro_observations == {}
    assert type(result.macro_observations).__name__ == "mappingproxy"

    service.macro_repo.get_series.assert_not_called()
    service.macro_repo.get_latest_as_of.assert_not_called()


def test_get_snapshot_macro_observations_are_immutable():
    service = make_service()
    service.security_repo.get_by_symbol.return_value = make_security()

    series = Mock(id=7)
    service.macro_repo.get_series.return_value = series
    service.macro_repo.get_latest_as_of.return_value = ["macro"]

    result = service.get_snapshot(
        "AAPL",
        as_of=datetime(
            2026,
            8,
            20,
            tzinfo=timezone.utc,
        ),
        macro_series_ids=["gdp"],
    )

    assert result.macro_observations == {
        "GDP": ("macro",),
    }

    with pytest.raises(TypeError):
        result.macro_observations["CPI"] = ("other",)

    assert result.macro_observations == {
        "GDP": ("macro",),
    }