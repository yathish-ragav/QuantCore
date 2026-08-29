from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.research_observation import ResearchObservation


class ResearchObservationRepository:
    """Persistence operations for immutable research observations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_identity(
        self,
        *,
        security_id: int,
        as_of: datetime,
        observation_key: str,
        definition_version: str,
    ) -> ResearchObservation | None:
        return self.db.scalar(
            select(ResearchObservation).where(
                ResearchObservation.security_id == security_id,
                ResearchObservation.as_of == as_of,
                ResearchObservation.observation_key == observation_key,
                ResearchObservation.definition_version == definition_version,
            )
        )

    def create(self, **kwargs) -> ResearchObservation:
        observation = ResearchObservation(**kwargs)
        self.db.add(observation)
        return observation

    def get_for_security_as_of(
        self,
        security_id: int,
        as_of: datetime,
    ) -> list[ResearchObservation]:
        stmt = (
            select(ResearchObservation)
            .where(
                ResearchObservation.security_id == security_id,
                ResearchObservation.as_of == as_of,
            )
            .order_by(
                ResearchObservation.observation_key,
                ResearchObservation.definition_version,
                ResearchObservation.id,
            )
        )
        return list(self.db.scalars(stmt).all())
