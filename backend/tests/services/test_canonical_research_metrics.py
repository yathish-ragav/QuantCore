from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from quantcore.core.enums import FinancialPeriodType
from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.canonical_research_metrics import (
    get_canonical_research_metric_definitions,
)
from quantcore.services.pit_alignment_service import PITAlignedSnapshot
from quantcore.services.research_observation_definition_service import (
    ResearchObservationDefinitionService,
)


def make_row(**values):
    defaults = {
        "id": 1,
        "statement_id": 10,
        "revision_number": 1,
        "fiscal_date": date(2026, 6, 30),
        "period_type": FinancialPeriodType.TTM,
        "known_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "total_revenue": 1_000.0,
        "net_income": 120.0,
        "operating_income": 180.0,
        "free_cash_flow": 150.0,
        "total_debt": 400.0,
        "total_equity": 800.0,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def make_snapshot(*, income=(), balance=(), cash_flow=()):
    return PITAlignedSnapshot(
        symbol="AAPL",
        security_id=10,
        company_id=20,
        as_of=datetime(2026, 8, 20, tzinfo=timezone.utc),
        prices=(),
        income_statements=tuple(income),
        balance_sheets=tuple(balance),
        cash_flow_statements=tuple(cash_flow),
        corporate_actions=(),
        sec_xbrl_facts=(),
        macro_observations={},
    )


def definition(key):
    return next(
        item
        for item in get_canonical_research_metric_definitions()
        if item.observation_key == key
    )


def test_canonical_registry_contains_versioned_metric_identities():
    definitions = get_canonical_research_metric_definitions()

    assert [(item.observation_key, item.definition_version) for item in definitions] == [
        ("net_margin", "1"),
        ("operating_margin", "1"),
        ("fcf_margin", "1"),
        ("debt_to_equity", "1"),
    ]


def test_definition_service_uses_canonical_definitions_by_default():
    service = ResearchObservationDefinitionService(None)

    assert service.definition_registry.get("net_margin", "1").observation_key == "net_margin"
    assert service.definition_registry.get("debt_to_equity", "1").definition_version == "1"


def test_net_margin_uses_latest_pit_known_ttm_row():
    older = make_row(id=1, fiscal_date=date(2026, 3, 31), net_income=100.0)
    latest = make_row(id=2, fiscal_date=date(2026, 6, 30), net_income=120.0)

    result = definition("net_margin").compute(make_snapshot(income=(latest, older)))

    assert result.value_numeric == pytest.approx(0.12)
    assert result.unit == "ratio"
    assert result.input_manifest["source"]["revision_id"] == 2
    assert result.input_manifest["formula"] == {
        "numerator": "net_income",
        "denominator": "total_revenue",
    }


def test_operating_margin_rejects_zero_revenue():
    row = make_row(total_revenue=0.0)

    with pytest.raises(InvalidInputError, match="denominator is zero"):
        definition("operating_margin").compute(make_snapshot(income=(row,)))


def test_fcf_margin_uses_matching_ttm_income_and_cash_flow_period():
    income = make_row(total_revenue=1_000.0)
    cash_flow = make_row(free_cash_flow=150.0)

    result = definition("fcf_margin").compute(
        make_snapshot(income=(income,), cash_flow=(cash_flow,))
    )

    assert result.value_numeric == pytest.approx(0.15)
    assert result.input_manifest["source"]["income_fiscal_date"] == "2026-06-30"
    assert result.input_manifest["source"]["cash_flow_fiscal_date"] == "2026-06-30"


def test_fcf_margin_rejects_mismatched_periods():
    income = make_row(fiscal_date=date(2026, 6, 30))
    cash_flow = make_row(fiscal_date=date(2026, 3, 31))

    with pytest.raises(InvalidInputError, match="periods do not match"):
        definition("fcf_margin").compute(
            make_snapshot(income=(income,), cash_flow=(cash_flow,))
        )


def test_debt_to_equity_requires_instant_balance_sheet():
    row = make_row(period_type=FinancialPeriodType.INSTANT)

    result = definition("debt_to_equity").compute(make_snapshot(balance=(row,)))

    assert result.value_numeric == pytest.approx(0.5)
    assert result.input_manifest["source"]["period_type"] == "INSTANT"


def test_metric_requires_expected_period_type():
    quarterly = make_row(period_type=FinancialPeriodType.QUARTERLY)

    with pytest.raises(ResourceNotFoundError, match="TTM"):
        definition("net_margin").compute(make_snapshot(income=(quarterly,)))
