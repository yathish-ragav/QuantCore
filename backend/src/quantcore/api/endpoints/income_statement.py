from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_income_statement_service
from quantcore.schemas.responses import (
    IncomeStatementResponse,
    IncomeStatementSyncResponse,
)
from quantcore.services.income_statement_service import (
    IncomeStatementService,
)


router = APIRouter(
    prefix="/income-statements",
    tags=["Income Statements"],
)


@router.get(
    "/{symbol}",
    response_model=list[IncomeStatementResponse],
)
def get_income_statements(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Return the latest statement revisions known at this timestamp.",
    ),
    service: IncomeStatementService = Depends(
        get_income_statement_service
    ),
):
    normalized_symbol = symbol.strip().upper()

    statements = service.get_income_statements(
        normalized_symbol,
        as_of=as_of,
    )

    return [
        IncomeStatementResponse(
            fiscal_date=statement.fiscal_date,
            period_start=statement.period_start,
            fiscal_year=statement.fiscal_year,
            fiscal_period=statement.fiscal_period,
            period_type=statement.period_type,
            filing_date=statement.filing_date,
            filing_form=statement.filing_form,
            accession_number=statement.accession_number,
            total_revenue=statement.total_revenue,
            gross_profit=statement.gross_profit,
            operating_income=statement.operating_income,
            net_income=statement.net_income,
            eps=statement.eps,
            shares_outstanding=(
                statement.shares_outstanding
            ),
        )
        for statement in statements
    ]


@router.post(
    "/{symbol}/sync",
    response_model=IncomeStatementSyncResponse,
)
def sync_income_statements(
    symbol: str,
    service: IncomeStatementService = Depends(
        get_income_statement_service
    ),
):
    normalized_symbol = symbol.strip().upper()

    result = service.sync_income_statements(
        normalized_symbol
    )

    return IncomeStatementSyncResponse(
        symbol=normalized_symbol,
        statements_added=result.created,
        statements_updated=result.updated,
        statements_unchanged=result.unchanged,
        records_processed=result.records_processed,
    )
