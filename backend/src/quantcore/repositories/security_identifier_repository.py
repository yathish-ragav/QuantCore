from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quantcore.core.exceptions import DataValidationError
from quantcore.models.security_identifier import SecurityIdentifier
from quantcore.core.security_identity import SecurityIdentifierType


class SecurityIdentifierRepository:
    """Persistence and PIT resolution for external security identifiers."""

    def __init__(self, db: Session):
        self.db = db

    def get_exact(
        self,
        security_id: int,
        identifier_type: SecurityIdentifierType,
        namespace: str,
        value: str,
        valid_from: date,
        known_at: datetime,
    ) -> SecurityIdentifier | None:
        return self.db.scalar(
            select(SecurityIdentifier).where(
                SecurityIdentifier.security_id == security_id,
                SecurityIdentifier.identifier_type == identifier_type.value,
                SecurityIdentifier.namespace == namespace,
                SecurityIdentifier.value == value,
                SecurityIdentifier.valid_from == valid_from,
                SecurityIdentifier.known_at == known_at,
            )
        )

    def get_for_security_as_of(
        self,
        security_id: int,
        *,
        effective_on: date,
        known_at: datetime,
    ) -> list[SecurityIdentifier]:
        # Select the latest known revision of each effective interval first.
        # A later-known correction may backdate ``valid_to``; applying the
        # effective-date predicate inside the ranking query would discard that
        # correction and leak the older open-ended mapping into PIT reads.
        ranked = (
            select(
                SecurityIdentifier.id.label("identifier_id"),
                func.row_number().over(
                    partition_by=(
                        SecurityIdentifier.identifier_type,
                        SecurityIdentifier.namespace,
                        SecurityIdentifier.valid_from,
                    ),
                    order_by=(
                        SecurityIdentifier.known_at.desc(),
                        SecurityIdentifier.id.desc(),
                    ),
                ).label("revision_rank"),
            )
            .where(
                SecurityIdentifier.security_id == security_id,
                SecurityIdentifier.known_at <= known_at,
            )
            .subquery()
        )
        stmt = (
            select(SecurityIdentifier)
            .join(ranked, SecurityIdentifier.id == ranked.c.identifier_id)
            .where(
                ranked.c.revision_rank == 1,
                SecurityIdentifier.valid_from <= effective_on,
                (SecurityIdentifier.valid_to.is_(None))
                | (SecurityIdentifier.valid_to > effective_on),
            )
            .order_by(SecurityIdentifier.identifier_type.asc())
        )
        return list(self.db.scalars(stmt).all())

    def resolve_as_of(
        self,
        identifier_type: SecurityIdentifierType,
        namespace: str,
        value: str,
        *,
        effective_on: date,
        known_at: datetime,
    ) -> SecurityIdentifier | None:
        # The effective interval is evaluated only after selecting the latest
        # known revision for the requested identifier value/interval.
        ranked = (
            select(
                SecurityIdentifier.id.label("identifier_id"),
                func.row_number().over(
                    partition_by=(
                        SecurityIdentifier.security_id,
                        SecurityIdentifier.valid_from,
                    ),
                    order_by=(
                        SecurityIdentifier.known_at.desc(),
                        SecurityIdentifier.id.desc(),
                    ),
                ).label("revision_rank"),
            )
            .where(
                SecurityIdentifier.identifier_type == identifier_type.value,
                SecurityIdentifier.namespace == namespace,
                SecurityIdentifier.value == value,
                SecurityIdentifier.known_at <= known_at,
            )
            .subquery()
        )
        candidates = list(
            self.db.scalars(
                select(SecurityIdentifier)
                .join(ranked, SecurityIdentifier.id == ranked.c.identifier_id)
                .where(
                    ranked.c.revision_rank == 1,
                    SecurityIdentifier.valid_from <= effective_on,
                    (SecurityIdentifier.valid_to.is_(None))
                    | (SecurityIdentifier.valid_to > effective_on),
                )
            ).all()
        )

        if not candidates:
            return None

        candidates.sort(
            key=lambda row: (row.known_at, row.valid_from, row.id),
            reverse=True,
        )
        latest = candidates[0]

        same_knowledge = [
            row for row in candidates if row.known_at == latest.known_at
        ]
        security_ids = {row.security_id for row in same_knowledge}
        if len(security_ids) > 1:
            raise DataValidationError(
                f"Identifier '{value}' of type '{identifier_type.value}' "
                "resolves to multiple securities at the same knowledge boundary."
            )
        return latest

    def get_for_security(
        self,
        security_id: int,
        identifier_type: SecurityIdentifierType | None = None,
        namespace: str | None = None,
    ) -> list[SecurityIdentifier]:
        conditions = [SecurityIdentifier.security_id == security_id]
        if identifier_type is not None:
            conditions.append(
                SecurityIdentifier.identifier_type == identifier_type.value
            )
        if namespace is not None:
            conditions.append(SecurityIdentifier.namespace == namespace)
        stmt = select(SecurityIdentifier).where(*conditions).order_by(
            SecurityIdentifier.identifier_type.asc(),
            SecurityIdentifier.valid_from.asc(),
            SecurityIdentifier.known_at.asc(),
            SecurityIdentifier.id.asc(),
        )
        return list(self.db.scalars(stmt).all())

    def create(self, **kwargs) -> SecurityIdentifier:
        identifier = SecurityIdentifier(**kwargs)
        self.db.add(identifier)
        return identifier
