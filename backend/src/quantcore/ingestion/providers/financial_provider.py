from abc import ABC, abstractmethod

from quantcore.schemas.income_statement import IncomeStatementData


class FinancialDataProvider(ABC):

    @abstractmethod
    def get_income_statements(
        self,
        symbol: str,
    ) -> list[IncomeStatementData]:
        pass