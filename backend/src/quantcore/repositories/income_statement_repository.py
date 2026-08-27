from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.core.enums import FinancialPeriodType
from quantcore.models.income_statement import IncomeStatement


class IncomeStatementRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_company_and_date(
        self,
        company_id: int,
        fiscal_date: date,
        period_type: FinancialPeriodType = FinancialPeriodType.ANNUAL,
    ) -> IncomeStatement | None:

        stmt = (
            select(IncomeStatement)
            .where(
                IncomeStatement.company_id == company_id,
                IncomeStatement.fiscal_date == fiscal_date,
                IncomeStatement.period_type == period_type,
            )
        )

        return self.db.scalar(stmt)

    def get_for_company(
        self,
        company_id: int,
    ) -> list[IncomeStatement]:

        stmt = (
            select(IncomeStatement)
            .where(
                IncomeStatement.company_id == company_id
            )
            .order_by(
                IncomeStatement.fiscal_date.desc()
            )
        )

        return list(
            self.db.scalars(stmt)
        )

    def create(
        self,
        **kwargs,
    ) -> IncomeStatement:

        statement = IncomeStatement(**kwargs)

        self.db.add(statement)

        return statement