from dataclasses import dataclass
from datetime import datetime, timezone

from quantcore.core.enums import FinancialStatementType
from quantcore.models.provenance import DataSource
from quantcore.repositories.financial_statement_revision_repository import (
    FinancialStatementRevisionRepository,
)

COMMON_FIELDS = (
    "fiscal_date", "period_start", "fiscal_year", "fiscal_period",
    "period_type", "filing_date", "filing_form", "accession_number",
)
INCOME_FIELDS = ("total_revenue", "gross_profit", "operating_income", "net_income", "eps", "shares_outstanding", "weighted_average_shares_outstanding")
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


def resolve_statement_known_at(
    statement,
    *,
    source: DataSource,
    fetched_at: datetime,
    filing_repo=None,
):
    """Resolve the PIT publication timestamp for a normalized statement.

    SEC-derived statements use the authoritative filing acceptance timestamp
    when the corresponding accession is available. Fetch time is only a
    fallback when SEC filing metadata is unavailable. Non-SEC providers retain
    fetch-time semantics because their filing timestamps are not authoritative
    EDGAR publication timestamps.
    """
    if source is DataSource.SEC and filing_repo is not None:
        accession = getattr(statement, "accession_number", None)
        if accession:
            filing = filing_repo.get_by_accession(accession)
            if filing is not None and filing.acceptance_datetime is not None:
                return filing.acceptance_datetime
    return fetched_at

def build_statement_known_at_cache(
    statements,
    *,
    source: DataSource,
    fetched_at: datetime,
    filing_repo=None,
) -> dict:
    """Preload SEC filing acceptance timestamps for a statement batch in one query."""
    cache = {}
    accessions = {
        getattr(statement, "accession_number", None)
        for statement in statements
        if getattr(statement, "accession_number", None)
    }
    if source is DataSource.SEC and filing_repo is not None and accessions:
        filings = filing_repo.get_by_accessions(accessions)
        for accession in accessions:
            filing = filings.get(accession)
            cache[accession] = (
                filing.acceptance_datetime
                if filing is not None and filing.acceptance_datetime is not None
                else fetched_at
            )
    for statement in statements:
        accession = getattr(statement, "accession_number", None)
        if accession not in cache:
            cache[accession] = fetched_at
    return cache


def cached_statement_known_at(
    statement,
    *,
    source: DataSource,
    fetched_at: datetime,
    filing_repo=None,
    cache: dict | None = None,
):
    key = getattr(statement, "accession_number", None)
    if cache is not None and key in cache:
        return cache[key]
    value = resolve_statement_known_at(
        statement,
        source=source,
        fetched_at=fetched_at,
        filing_repo=filing_repo,
    )
    if cache is not None:
        cache[key] = value
    return value

def create_revision(revision_repo, statement, statement_type, source, known_at, revision_number=None):
    values = {field: getattr(statement, field) for field in STATEMENT_FIELDS[statement_type]}
    values.update({
        "statement_type": statement_type,
        "statement_id": statement.id,
        "company_id": statement.company_id,
        "revision_number": (
            revision_number
            if revision_number is not None
            else revision_repo.get_next_revision_number(statement_type, statement.id)
        ),
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
