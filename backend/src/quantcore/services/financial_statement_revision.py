from dataclasses import dataclass
from datetime import datetime, timezone

from quantcore.core.enums import FinancialStatementType
from quantcore.repositories.financial_statement_revision_repository import (
    FinancialStatementRevisionRepository,
)

COMMON_FIELDS = (
    "fiscal_date", "period_start", "fiscal_year", "fiscal_period",
    "period_type", "filing_date", "filing_form", "accession_number",
)
INCOME_FIELDS = ("total_revenue", "gross_profit", "operating_income", "net_income", "eps", "shares_outstanding")
BALANCE_FIELDS = (
    "cash_and_cash_equivalents", "short_term_investments", "accounts_receivable",
    "inventory", "total_current_assets", "property_plant_equipment_net",
    "goodwill", "intangible_assets", "total_assets", "accounts_payable",
    "short_term_debt", "total_current_liabilities", "long_term_debt",
    "total_liabilities", "total_equity", "retained_earnings", "total_debt",
    "net_debt", "working_capital",
)
CASH_FLOW_FIELDS = (
    "operating_cash_flow", "capital_expenditure", "free_cash_flow",
    "investing_cash_flow", "financing_cash_flow", "depreciation_and_amortization",
    "stock_based_compensation", "dividends_paid", "share_repurchases",
    "net_change_in_cash",
)
STATEMENT_FIELDS = {
    FinancialStatementType.INCOME: COMMON_FIELDS + INCOME_FIELDS,
    FinancialStatementType.BALANCE_SHEET: COMMON_FIELDS + BALANCE_FIELDS,
    FinancialStatementType.CASH_FLOW: COMMON_FIELDS + CASH_FLOW_FIELDS,
}

@dataclass(frozen=True)
class FinancialStatementSyncResult:
    created: int
    updated: int
    unchanged: int
    records_processed: int


def statement_changed(existing, data, statement_type):
    return any(getattr(existing, field) != getattr(data, field) for field in STATEMENT_FIELDS[statement_type])


def apply_statement_data(existing, data, statement_type):
    for field in STATEMENT_FIELDS[statement_type]:
        setattr(existing, field, getattr(data, field))


def create_revision(revision_repo, statement, statement_type, source, known_at):
    values = {field: getattr(statement, field) for field in STATEMENT_FIELDS[statement_type]}
    values.update({
        "statement_type": statement_type,
        "statement_id": statement.id,
        "company_id": statement.company_id,
        "revision_number": revision_repo.get_next_revision_number(statement_type, statement.id),
        "source": source,
        "known_at": known_at,
        "source_reference": getattr(statement, "source_reference", None),
    })
    return revision_repo.create(**values)


def normalize_as_of(as_of):
    if as_of is None:
        return None
    if as_of.tzinfo is None:
        return as_of.replace(tzinfo=timezone.utc)
    return as_of


def get_statements_as_of(revision_repo: FinancialStatementRevisionRepository, company_id: int, statement_type, as_of: datetime):
    return revision_repo.get_latest_for_company_as_of(company_id, statement_type, normalize_as_of(as_of))
