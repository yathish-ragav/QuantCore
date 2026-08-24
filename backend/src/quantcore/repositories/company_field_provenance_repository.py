from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.models.provenance import (
    CompanyField,
    CompanyFieldProvenance,
    DataSource,
)


class CompanyFieldProvenanceRepository:
    """Persist the current provider ownership of Company fields."""

    def __init__(self, db: Session):
        self.db = db

    def get(
        self,
        company_id: int,
        field_name: CompanyField,
    ) -> CompanyFieldProvenance | None:
        stmt = (
            select(CompanyFieldProvenance)
            .where(
                CompanyFieldProvenance.company_id == company_id,
                CompanyFieldProvenance.field_name == field_name,
            )
        )

        return self.db.scalar(stmt)

    def upsert(
        self,
        company_id: int,
        field_name: CompanyField,
        source: DataSource,
        fetched_at: datetime,
        source_reference: str | None = None,
    ) -> CompanyFieldProvenance:
        existing = self.get(company_id, field_name)

        if existing is None:
            existing = CompanyFieldProvenance(
                company_id=company_id,
                field_name=field_name,
                source=source,
                fetched_at=fetched_at,
                source_reference=source_reference,
            )
            self.db.add(existing)
            return existing

        existing.source = source
        existing.fetched_at = fetched_at
        existing.source_reference = source_reference

        return existing
