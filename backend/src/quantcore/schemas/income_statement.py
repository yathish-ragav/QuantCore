from datetime import date

from quantcore.schemas.financial_statement import FinancialStatementMetadata


class IncomeStatementData(FinancialStatementMetadata):
    fiscal_date: date

    total_revenue: float | None = None

    gross_profit: float | None = None

    operating_income: float | None = None

    net_income: float | None = None

    eps: float | None = None

    shares_outstanding: int | None = None