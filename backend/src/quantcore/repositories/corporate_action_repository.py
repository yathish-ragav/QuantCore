from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.core.enums import CorporateActionType
from quantcore.models.corporate_action import CorporateAction


class CorporateActionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_security(self, security_id: int) -> list[CorporateAction]:
        stmt = (
            select(CorporateAction)
            .where(CorporateAction.security_id == security_id)
            .order_by(
                CorporateAction.effective_date.desc(),
                CorporateAction.action_type,
            )
        )
        return list(self.db.scalars(stmt).all())

    def get_by_identity(
        self,
        security_id: int,
        effective_date,
        action_type: CorporateActionType,
    ) -> CorporateAction | None:
        return self.db.scalar(
            select(CorporateAction).where(
                CorporateAction.security_id == security_id,
                CorporateAction.effective_date == effective_date,
                CorporateAction.action_type == action_type,
            )
        )

    def create(self, **kwargs) -> CorporateAction:
        action = CorporateAction(**kwargs)
        self.db.add(action)
        return action
