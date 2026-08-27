from datetime import date

from quantcore.schemas.financial_statement import FinancialStatementMetadata


class BalanceSheetData(FinancialStatementMetadata):
    fiscal_date: date

    cash_and_cash_equivalents: float | None = None
    short_term_investments: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    total_current_assets: float | None = None
    property_plant_equipment_net: float | None = None
    goodwill: float | None = None
    intangible_assets: float | None = None
    total_assets: float | None = None

    accounts_payable: float | None = None
    short_term_debt: float | None = None
    total_current_liabilities: float | None = None
    long_term_debt: float | None = None
    total_liabilities: float | None = None

    total_equity: float | None = None
    retained_earnings: float | None = None

    total_debt: float | None = None
    net_debt: float | None = None
    working_capital: float | None = None
