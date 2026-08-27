from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quantcore.models.corporate_action_revision import CorporateActionRevision
from quantcore.models.corporate_action import CorporateAction


class CorporateActionRevisionRepository:
    """Persistence operations for immutable corporate-action revisions."""

    def __init__(self, db: Session):
        self.db = db

    def get_next_revision_number(self, action_id: int) -> int:
        current = self.db.scalar(
            select(func.max(CorporateActionRevision.revision_number)).where(
                CorporateActionRevision.action_id == action_id
            )
        )
        return (current or 0) + 1

    def create(self, **kwargs) -> CorporateActionRevision:
        revision = CorporateActionRevision(**kwargs)
        self.db.add(revision)
        return revision

    def get_for_action(self, action_id: int) -> list[CorporateActionRevision]:
        stmt = (
            select(CorporateActionRevision)
            .where(CorporateActionRevision.action_id == action_id)
            .order_by(CorporateActionRevision.revision_number)
        )
        return list(self.db.scalars(stmt).all())

    def get_latest_for_security_as_of(
        self,
        security_id: int,
        as_of: datetime,
    ) -> list[CorporateActionRevision]:
        ranked = (
            select(
                CorporateActionRevision.id.label("revision_id"),
                func.row_number().over(
                    partition_by=(
                        CorporateActionRevision.action_id,
                    ),
                    order_by=(
                        CorporateActionRevision.known_at.desc(),
                        CorporateActionRevision.revision_number.desc(),
                    ),
                ).label("revision_rank"),
            )
            .where(
                CorporateActionRevision.security_id == security_id,
                CorporateActionRevision.known_at <= as_of,
            )
            .subquery()
        )

        stmt = (
            select(CorporateActionRevision)
            .join(ranked, ranked.c.revision_id == CorporateActionRevision.id)
            .where(ranked.c.revision_rank == 1)
            .order_by(
                CorporateActionRevision.effective_date.asc(),
                CorporateActionRevision.id.asc(),
            )
        )
        return list(self.db.scalars(stmt).all())
