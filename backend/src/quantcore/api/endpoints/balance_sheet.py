from fastapi import APIRouter, Depends

from quantcore.api.dependencies import get_balance_sheet_service
from quantcore.schemas.responses import (
    BalanceSheetResponse,
    BalanceSheetSyncResponse,
)
from quantcore.services.balance_sheet_service import BalanceSheetService


router = APIRouter(
    prefix="/balance-sheets",
    tags=["Balance Sheets"],
)


@router.get(
    "/{symbol}",
    response_model=list[BalanceSheetResponse],
)
def get_balance_sheets(
    symbol: str,
    service: BalanceSheetService = Depends(
        get_balance_sheet_service
    ),
):
    normalized_symbol = symbol.strip().upper()
    statements = service.get_balance_sheets(normalized_symbol)

    return [
        BalanceSheetResponse(
            fiscal_date=statement.fiscal_date,
            cash_and_cash_equivalents=(
                statement.cash_and_cash_equivalents
            ),
            short_term_investments=(
                statement.short_term_investments
            ),
            accounts_receivable=statement.accounts_receivable,
            inventory=statement.inventory,
            total_current_assets=statement.total_current_assets,
            property_plant_equipment_net=(
                statement.property_plant_equipment_net
            ),
            goodwill=statement.goodwill,
            intangible_assets=statement.intangible_assets,
            total_assets=statement.total_assets,
            accounts_payable=statement.accounts_payable,
            short_term_debt=statement.short_term_debt,
            total_current_liabilities=(
                statement.total_current_liabilities
            ),
            long_term_debt=statement.long_term_debt,
            total_liabilities=statement.total_liabilities,
            total_equity=statement.total_equity,
            retained_earnings=statement.retained_earnings,
            total_debt=statement.total_debt,
            net_debt=statement.net_debt,
            working_capital=statement.working_capital,
        )
        for statement in statements
    ]


@router.post(
    "/{symbol}/sync",
    response_model=BalanceSheetSyncResponse,
)
def sync_balance_sheets(
    symbol: str,
    service: BalanceSheetService = Depends(
        get_balance_sheet_service
    ),
):
    normalized_symbol = symbol.strip().upper()
    created = service.sync_balance_sheets(normalized_symbol)

    return BalanceSheetSyncResponse(
        symbol=normalized_symbol,
        statements_added=len(created),
    )
