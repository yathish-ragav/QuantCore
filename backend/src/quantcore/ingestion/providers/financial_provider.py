from abc import ABC, abstractmethod

from quantcore.schemas.cash_flow_statement import CashFlowStatementData
from quantcore.schemas.income_statement import IncomeStatementData


class FinancialDataProvider(ABC):

    @abstractmethod
    def get_income_statements(
        self,
        symbol: str,
    ) -> list[IncomeStatementData]:
        pass

    @abstractmethod
    def get_cash_flow_statements(
        self,
        symbol: str,
    ) -> list[CashFlowStatementData]:
        pass