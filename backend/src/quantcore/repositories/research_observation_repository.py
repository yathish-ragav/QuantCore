from datetime import datetime

from sqlalchemy import func, select
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

    def get_latest_for_security_as_of(
        self,
        security_id: int,
        as_of: datetime,
    ) -> list[ResearchObservation]:
        """Return the latest observation for each definition known by ``as_of``."""
        ranked = (
            select(
                ResearchObservation.id.label("observation_id"),
                func.row_number()
                .over(
                    partition_by=(
                        ResearchObservation.observation_key,
                        ResearchObservation.definition_version,
                    ),
                    order_by=(
                        ResearchObservation.as_of.desc(),
                        ResearchObservation.id.desc(),
                    ),
                )
                .label("observation_rank"),
            )
            .where(
                ResearchObservation.security_id == security_id,
                ResearchObservation.as_of <= as_of,
            )
            .subquery()
        )

        stmt = (
            select(ResearchObservation)
            .join(
                ranked,
                ranked.c.observation_id == ResearchObservation.id,
            )
            .where(ranked.c.observation_rank == 1)
            .order_by(
                ResearchObservation.observation_key,
                ResearchObservation.definition_version,
                ResearchObservation.as_of.desc(),
                ResearchObservation.id.desc(),
            )
        )
        return list(self.db.scalars(stmt).all())
