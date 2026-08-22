from fastapi import APIRouter, Depends

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
    service: IncomeStatementService = Depends(
        get_income_statement_service
    ),
):
    normalized_symbol = symbol.strip().upper()

    statements = service.get_income_statements(
        normalized_symbol
    )

    return [
        IncomeStatementResponse(
            fiscal_date=statement.fiscal_date,
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

    created = service.sync_income_statements(
        normalized_symbol
    )

    return IncomeStatementSyncResponse(
        symbol=normalized_symbol,
        statements_added=len(created),
    )
