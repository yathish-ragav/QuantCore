from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.balance_sheet import BalanceSheet


class BalanceSheetRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_company_and_date(
        self,
        company_id: int,
        fiscal_date: date,
    ) -> BalanceSheet | None:
        stmt = (
            select(BalanceSheet)
            .where(
                BalanceSheet.company_id == company_id,
                BalanceSheet.fiscal_date == fiscal_date,
            )
        )

        return self.db.scalar(stmt)

    def get_for_company(
        self,
        company_id: int,
    ) -> list[BalanceSheet]:
        stmt = (
            select(BalanceSheet)
            .where(BalanceSheet.company_id == company_id)
            .order_by(BalanceSheet.fiscal_date.desc())
        )

        return list(self.db.scalars(stmt))

    def create(self, **kwargs) -> BalanceSheet:
        statement = BalanceSheet(**kwargs)
        self.db.add(statement)
        return statement
