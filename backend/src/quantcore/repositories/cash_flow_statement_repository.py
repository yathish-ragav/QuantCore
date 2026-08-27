from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.core.enums import FinancialPeriodType
from quantcore.models.cash_flow_statement import CashFlowStatement


class CashFlowStatementRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_company_and_date(
        self,
        company_id: int,
        fiscal_date: date,
        period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL,
    ) -> CashFlowStatement | None:

        stmt = (
            select(CashFlowStatement)
            .where(
                CashFlowStatement.company_id == company_id,
                CashFlowStatement.fiscal_date == fiscal_date,
                CashFlowStatement.period_type == period_type,
            )
        )

        return self.db.scalar(stmt)

    def get_for_company(
        self,
        company_id: int,
    ) -> list[CashFlowStatement]:

        stmt = (
            select(CashFlowStatement)
            .where(
                CashFlowStatement.company_id == company_id
            )
            .order_by(
                CashFlowStatement.fiscal_date.desc()
            )
        )

        return list(
            self.db.scalars(stmt)
        )

    def create(
        self,
        **kwargs,
    ) -> CashFlowStatement:

        statement = CashFlowStatement(**kwargs)

        self.db.add(statement)

        return statement
