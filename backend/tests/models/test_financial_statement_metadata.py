from datetime import date

from quantcore.core.enums import FinancialPeriodType
from quantcore.schemas.balance_sheet import BalanceSheetData
from quantcore.schemas.cash_flow_statement import CashFlowStatementData
from quantcore.schemas.income_statement import IncomeStatementData


def test_financial_statement_metadata_defaults_to_annual():
    data = IncomeStatementData(fiscal_date=date(2024, 9, 28))
    assert data.period_type is FinancialPeriodType.ANNUAL
    assert data.fiscal_year is None


def test_financial_statement_metadata_supports_quarterly_duration():
    data = CashFlowStatementData(
        fiscal_date=date(2025, 3, 31),
        period_start=date(2025, 1, 1),
        fiscal_year=2025,
        fiscal_period="Q1",
        period_type=FinancialPeriodType.QUARTERLY,
        filing_date=date(2025, 5, 2),
        filing_form="10-Q",
        accession_number="0000000000-25-000001",
    )
    assert data.period_type is FinancialPeriodType.QUARTERLY
    assert data.period_start == date(2025, 1, 1)
    assert data.filing_form == "10-Q"


def test_balance_sheet_metadata_supports_instant_period():
    data = BalanceSheetData(
        fiscal_date=date(2025, 9, 27),
        fiscal_year=2025,
        fiscal_period="FY",
        period_type=FinancialPeriodType.INSTANT,
        filing_date=date(2025, 11, 1),
        filing_form="10-K",
    )
    assert data.period_type is FinancialPeriodType.INSTANT
    assert data.period_start is None
