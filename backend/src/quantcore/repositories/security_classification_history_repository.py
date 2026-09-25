from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quantcore.core.enums import SecurityType
from quantcore.models.provenance import DataSource
from quantcore.models.security_classification_history import SecurityClassificationHistory


class SecurityClassificationHistoryRepository:
    """Bitemporal instrument-classification persistence and PIT resolution."""

    def __init__(self, db: Session):
        self.db = db

    def get_current(self, security_id: int) -> SecurityClassificationHistory | None:
        return self.db.scalar(
            select(SecurityClassificationHistory).where(
                SecurityClassificationHistory.security_id == security_id,
                SecurityClassificationHistory.is_current.is_(True),
                SecurityClassificationHistory.effective_to.is_(None),
            )
        )

    def record_observation(
        self,
        security_id: int,
        security_type: SecurityType,
        observed_at: datetime,
        *,
        source: DataSource | None = None,
        source_reference: str | None = None,
    ) -> SecurityClassificationHistory:
        if observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")

        current = self.get_current(security_id)
        observed_date = observed_at.date()
        if current is None:
            history = SecurityClassificationHistory(
                security_id=security_id,
                security_type=security_type,
                effective_from=observed_date,
                effective_to=None,
                known_at=observed_at,
                source=source,
                source_reference=source_reference,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                is_current=True,
            )
            self.db.add(history)
            return history

        current_known_at = current.known_at
        if current_known_at.tzinfo is None:
            current_known_at = current_known_at.replace(tzinfo=timezone.utc)
        if observed_at < current_known_at:
            raise ValueError("Classification observations cannot move known_at backward")

        current_last_seen_at = current.last_seen_at
        if current_last_seen_at.tzinfo is None:
            current_last_seen_at = current_last_seen_at.replace(tzinfo=timezone.utc)
        current.last_seen_at = max(current_last_seen_at, observed_at)
        if current.security_type is security_type:
            return current

        current.is_current = False
        revised = SecurityClassificationHistory(
            security_id=security_id,
            security_type=current.security_type,
            effective_from=current.effective_from,
            effective_to=observed_date,
            known_at=observed_at,
            source=source,
            source_reference=source_reference,
            first_seen_at=current.first_seen_at,
            last_seen_at=max(current.last_seen_at, observed_at),
            is_current=False,
        )
        self.db.add(revised)

        history = SecurityClassificationHistory(
            security_id=security_id,
            security_type=security_type,
            effective_from=observed_date,
            effective_to=None,
            known_at=observed_at,
            source=source,
            source_reference=source_reference,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
            is_current=True,
        )
        self.db.add(history)
        return history

    def get_as_of(
        self,
        security_id: int,
        *,
        effective_on: date,
        known_at: datetime,
    ) -> SecurityClassificationHistory | None:
        ranked = (
            select(
                SecurityClassificationHistory.id.label("id"),
                func.row_number()
                .over(
                    partition_by=(
                        SecurityClassificationHistory.security_id,
                        SecurityClassificationHistory.effective_from,
                    ),
                    order_by=(
                        SecurityClassificationHistory.known_at.desc(),
                        SecurityClassificationHistory.id.desc(),
                    ),
                )
                .label("revision_rank"),
            )
            .where(
                SecurityClassificationHistory.security_id == security_id,
                SecurityClassificationHistory.known_at <= known_at,
            )
            .subquery()
        )
        stmt = (
            select(SecurityClassificationHistory)
            .join(ranked, ranked.c.id == SecurityClassificationHistory.id)
            .where(
                ranked.c.revision_rank == 1,
                SecurityClassificationHistory.effective_from <= effective_on,
                (SecurityClassificationHistory.effective_to.is_(None))
                | (SecurityClassificationHistory.effective_to > effective_on),
            )
            .order_by(SecurityClassificationHistory.effective_from.desc())
        )
        return self.db.scalar(stmt)
