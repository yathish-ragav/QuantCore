from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.models.ingestion_lineage import IngestionLineage
from quantcore.models.provenance import DataSource


class IngestionLineageRepository:
    """Persist and query execution-to-entity ingestion provenance."""

    def __init__(self, db: Session):
        self.db = db

    def record_success(
        self,
        *,
        ingestion_run_id: int,
        dataset: IngestionDataset,
        scope: IngestionScope,
        company_id: int | None = None,
        security_id: int | None = None,
        source: DataSource | None = None,
        source_reference: str | None = None,
        records_processed: int,
        recorded_at: datetime,
    ) -> IngestionLineage:
        lineage = IngestionLineage(
            ingestion_run_id=ingestion_run_id,
            dataset=dataset,
            scope=scope,
            company_id=company_id,
            security_id=security_id,
            source=source,
            source_reference=source_reference,
            records_processed=records_processed,
            recorded_at=recorded_at,
        )
        self.db.add(lineage)
        self.db.flush()
        return lineage

    def list_for_run(self, ingestion_run_id: int) -> list[IngestionLineage]:
        stmt = (
            select(IngestionLineage)
            .where(IngestionLineage.ingestion_run_id == ingestion_run_id)
            .order_by(IngestionLineage.id)
        )
        return list(self.db.scalars(stmt).all())

    def list_for_entity(
        self,
        dataset: IngestionDataset,
        scope: IngestionScope,
        *,
        company_id: int | None = None,
        security_id: int | None = None,
    ) -> list[IngestionLineage]:
        stmt = select(IngestionLineage).where(
            IngestionLineage.dataset == dataset,
            IngestionLineage.scope == scope,
        )
        if company_id is not None:
            stmt = stmt.where(IngestionLineage.company_id == company_id)
        if security_id is not None:
            stmt = stmt.where(IngestionLineage.security_id == security_id)
        stmt = stmt.order_by(IngestionLineage.recorded_at, IngestionLineage.id)
        return list(self.db.scalars(stmt).all())
