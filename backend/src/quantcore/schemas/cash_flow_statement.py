from datetime import date

from pydantic import BaseModel


class CashFlowStatementData(BaseModel):
    fiscal_date: date

    operating_cash_flow: float | None = None

    capital_expenditure: float | None = None

    free_cash_flow: float | None = None

    investing_cash_flow: float | None = None

    financing_cash_flow: float | None = None

    depreciation_and_amortization: float | None = None

    stock_based_compensation: float | None = None

    dividends_paid: float | None = None

    share_repurchases: float | None = None

    net_change_in_cash: float | None = None
