from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from quantcore.core.enums import FinancialPeriodType, FinancialStatementType
from quantcore.models.provenance import DataSource
from quantcore.services.financial_period_materializer import FinancialPeriodMaterializer


def revision(
    statement_id,
    fiscal_date,
    period_start,
    period_type,
    known_at,
    *,
    fiscal_year=2026,
    **values,
):
    return SimpleNamespace(
        id=statement_id + 1000,
        statement_id=statement_id,
        fiscal_date=fiscal_date,
        period_start=period_start,
        period_type=period_type,
        fiscal_year=fiscal_year,
        filing_date=known_at.date(),
        filing_form="10-Q" if period_type is FinancialPeriodType.QUARTERLY else "10-K",
        accession_number=f"ACC-{statement_id}",
        known_at=known_at,
        fetched_at=known_at,
        **values,
    )


def test_quarters_contiguous_uses_fiscal_period_boundaries():
    known = datetime(2026, 8, 1, tzinfo=timezone.utc)
    quarters = [
        revision(1, date(2025, 9, 27), date(2025, 6, 29), FinancialPeriodType.QUARTERLY, known),
        revision(2, date(2025, 12, 27), date(2025, 9, 28), FinancialPeriodType.QUARTERLY, known),
        revision(3, date(2026, 3, 28), date(2025, 12, 28), FinancialPeriodType.QUARTERLY, known),
        revision(4, date(2026, 6, 27), date(2026, 3, 29), FinancialPeriodType.QUARTERLY, known),
    ]

    assert FinancialPeriodMaterializer._quarters_contiguous(quarters) is True


def test_q4_residual_is_deterministic_and_not_an_approximation():
    assert FinancialPeriodMaterializer._residual(1000.0, [200.0, 250.0, 300.0]) == 250.0
    assert FinancialPeriodMaterializer._residual(1000.0, [200.0, None, 300.0]) is None


def test_materialize_income_ttm_sums_four_quarters_and_preserves_known_at():
    service = FinancialPeriodMaterializer.__new__(FinancialPeriodMaterializer)
    service.db = Mock()
    service.revision_repo = Mock()
    service.income_repo = Mock()
    service.cash_flow_repo = Mock()

    known = [
        datetime(2026, 5, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 1, tzinfo=timezone.utc),
        datetime(2026, 11, 1, tzinfo=timezone.utc),
        datetime(2027, 2, 1, tzinfo=timezone.utc),
    ]
    quarters = [
        revision(1, date(2026, 3, 31), date(2026, 1, 1), FinancialPeriodType.QUARTERLY, known[0], total_revenue=100.0, gross_profit=40.0, operating_income=20.0, net_income=10.0),
        revision(2, date(2026, 6, 30), date(2026, 4, 1), FinancialPeriodType.QUARTERLY, known[1], total_revenue=110.0, gross_profit=44.0, operating_income=22.0, net_income=11.0),
        revision(3, date(2026, 9, 30), date(2026, 7, 1), FinancialPeriodType.QUARTERLY, known[2], total_revenue=120.0, gross_profit=48.0, operating_income=24.0, net_income=12.0),
        revision(4, date(2026, 12, 31), date(2026, 10, 1), FinancialPeriodType.QUARTERLY, known[3], total_revenue=130.0, gross_profit=52.0, operating_income=26.0, net_income=13.0),
    ]
    service.revision_repo.get_latest_for_company_as_of.return_value = quarters
    service.income_repo.get_by_company_and_date.return_value = None

    with patch("quantcore.services.financial_period_materializer.create_revision") as create_revision:
        changed = service._materialize_ttm(1, FinancialStatementType.INCOME, quarters)

    assert changed is True
    created = service.income_repo.create.call_args.kwargs
    assert created["period_type"] is FinancialPeriodType.TTM
    assert created["fiscal_date"] == date(2026, 12, 31)
    assert created["total_revenue"] == 460.0
    assert created["net_income"] == 46.0
    assert created["fiscal_period"] == "TTM"
    assert created["filing_date"] is None
    create_revision.assert_called_once()
    assert create_revision.call_args.args[4] == known[-1]


def test_materialize_q4_requires_three_contiguous_prior_quarters():
    known = datetime(2026, 8, 1, tzinfo=timezone.utc)
    annual = revision(10, date(2026, 12, 31), date(2026, 1, 1), FinancialPeriodType.ANNUAL, known, fiscal_year=2026, total_revenue=1000.0)
    quarters = [
        revision(1, date(2026, 3, 31), date(2026, 1, 1), FinancialPeriodType.QUARTERLY, known, fiscal_year=2026),
        revision(2, date(2026, 6, 30), date(2026, 4, 1), FinancialPeriodType.QUARTERLY, known, fiscal_year=2026),
    ]
    assert FinancialPeriodMaterializer._find_q4_inputs(annual, quarters) is None
