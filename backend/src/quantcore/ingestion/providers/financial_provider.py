from abc import ABC, abstractmethod
from typing import ClassVar

from quantcore.schemas.balance_sheet import BalanceSheetData
from quantcore.schemas.cash_flow_statement import CashFlowStatementData
from quantcore.schemas.income_statement import IncomeStatementData


class FinancialDataProvider(ABC):
    SOURCE: ClassVar[str]

    @abstractmethod
    def get_income_statements(
        self,
        symbol: str,
    ) -> list[IncomeStatementData]: ...

    @abstractmethod
    def get_cash_flow_statements(
        self,
        symbol: str,
    ) -> list[CashFlowStatementData]: ...

    def get_quarterly_income_statements(
        self,
        symbol: str,
    ) -> list[IncomeStatementData]:
        """Return normalized quarterly income statements when supported.

        Providers that do not expose safe quarterly observations may return
        an empty collection. The production SEC provider implements this
        capability from 10-Q XBRL facts.
        """
        return []

    def get_quarterly_cash_flow_statements(
        self,
        symbol: str,
    ) -> list[CashFlowStatementData]:
        """Return normalized quarterly cash-flow statements when supported."""
        return []

    @abstractmethod
    def get_balance_sheets(
        self,
        symbol: str,
    ) -> list[BalanceSheetData]: ...
