from datetime import datetime

from fastapi import APIRouter, Depends, Query

from quantcore.api.dependencies import get_cash_flow_statement_service
from quantcore.schemas.responses import (
    CashFlowStatementResponse,
    CashFlowStatementSyncResponse,
)
from quantcore.services.cash_flow_statement_service import (
    CashFlowStatementService,
)


router = APIRouter(
    prefix="/cash-flow-statements",
    tags=["Cash Flow Statements"],
)


@router.get(
    "/{symbol}",
    response_model=list[CashFlowStatementResponse],
)
def get_cash_flow_statements(
    symbol: str,
    as_of: datetime | None = Query(
        default=None,
        description="Return the latest statement revisions known at this timestamp.",
    ),
    service: CashFlowStatementService = Depends(
        get_cash_flow_statement_service
    ),
):
    normalized_symbol = symbol.strip().upper()

    statements = service.get_cash_flow_statements(
        normalized_symbol,
        as_of=as_of,
    )

    return [
        CashFlowStatementResponse(
            fiscal_date=statement.fiscal_date,
            period_start=statement.period_start,
            fiscal_year=statement.fiscal_year,
            fiscal_period=statement.fiscal_period,
            period_type=statement.period_type,
            filing_date=statement.filing_date,
            filing_form=statement.filing_form,
            accession_number=statement.accession_number,
            operating_cash_flow=(
                statement.operating_cash_flow
            ),
            capital_expenditure=(
                statement.capital_expenditure
            ),
            free_cash_flow=statement.free_cash_flow,
            investing_cash_flow=(
                statement.investing_cash_flow
            ),
            financing_cash_flow=(
                statement.financing_cash_flow
            ),
            depreciation_and_amortization=(
                statement.depreciation_and_amortization
            ),
            stock_based_compensation=(
                statement.stock_based_compensation
            ),
            dividends_paid=statement.dividends_paid,
            share_repurchases=(
                statement.share_repurchases
            ),
            net_change_in_cash=(
                statement.net_change_in_cash
            ),
        )
        for statement in statements
    ]


@router.post(
    "/{symbol}/sync",
    response_model=CashFlowStatementSyncResponse,
)
def sync_cash_flow_statements(
    symbol: str,
    service: CashFlowStatementService = Depends(
        get_cash_flow_statement_service
    ),
):
    normalized_symbol = symbol.strip().upper()

    result = service.sync_cash_flow_statements(
        normalized_symbol
    )

    return CashFlowStatementSyncResponse(
        symbol=normalized_symbol,
        statements_added=result.created,
        statements_updated=result.updated,
        statements_unchanged=result.unchanged,
        records_processed=result.records_processed,
    )
