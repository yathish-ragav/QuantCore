from datetime import date

from sqlalchemy.orm import Session

from quantcore.models.income_statement import IncomeStatement


class IncomeStatementRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_company_and_date(
        self,
        company_id: int,
        fiscal_date: date,
    ):
        return (
            self.db.query(IncomeStatement)
            .filter(
                IncomeStatement.company_id == company_id,
                IncomeStatement.fiscal_date == fiscal_date,
            )
            .first()
        )

    def create(self, **kwargs):
        statement = IncomeStatement(**kwargs)

        self.db.add(statement)

        return statement
