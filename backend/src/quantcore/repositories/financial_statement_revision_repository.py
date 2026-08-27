from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quantcore.core.enums import FinancialStatementType
from quantcore.models.financial_statement_revision import FinancialStatementRevision


class FinancialStatementRevisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_next_revision_number(self, statement_type: FinancialStatementType, statement_id: int) -> int:
        value = self.db.scalar(
            select(func.max(FinancialStatementRevision.revision_number)).where(
                FinancialStatementRevision.statement_type == statement_type,
                FinancialStatementRevision.statement_id == statement_id,
            )
        )
        return (value or 0) + 1

    def get_latest_for_company_as_of(
        self,
        company_id: int,
        statement_type: FinancialStatementType,
        as_of: datetime,
    ) -> list[FinancialStatementRevision]:
        ranked = (
            select(
                FinancialStatementRevision.id.label("revision_id"),
                func.row_number().over(
                    partition_by=FinancialStatementRevision.statement_id,
                    order_by=(
                        FinancialStatementRevision.known_at.desc(),
                        FinancialStatementRevision.revision_number.desc(),
                    ),
                ).label("revision_rank"),
            )
            .where(
                FinancialStatementRevision.company_id == company_id,
                FinancialStatementRevision.statement_type == statement_type,
                FinancialStatementRevision.known_at <= as_of,
            )
            .subquery()
        )

        stmt = (
            select(FinancialStatementRevision)
            .join(ranked, ranked.c.revision_id == FinancialStatementRevision.id)
            .where(ranked.c.revision_rank == 1)
            .order_by(
                FinancialStatementRevision.fiscal_date.desc(),
                FinancialStatementRevision.id.desc(),
            )
        )
        return list(self.db.scalars(stmt).all())

    def create(self, **kwargs) -> FinancialStatementRevision:
        revision = FinancialStatementRevision(**kwargs)
        self.db.add(revision)
        return revision
