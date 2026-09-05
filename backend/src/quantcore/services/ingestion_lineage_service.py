from __future__ import annotations

from datetime import datetime, timezone

from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.models.ingestion_lineage import IngestionLineage
from quantcore.models.provenance import DataSource
from quantcore.repositories.ingestion_lineage_repository import (
    IngestionLineageRepository,
)


class IngestionLineageService:
    """Provide deterministic execution-level ingestion lineage."""

    def __init__(self, db):
        self.repository = IngestionLineageRepository(db)

    def record_success(
        self,
        *,
        ingestion_run_id: int,
        dataset: IngestionDataset,
        scope: IngestionScope,
        company_id: int | None = None,
        security_id: int | None = None,
        source: str | DataSource | None = None,
        source_reference: str | None = None,
        records_processed: int,
        recorded_at: datetime | None = None,
    ) -> IngestionLineage:
        if ingestion_run_id <= 0:
            raise InvalidInputError("Ingestion run id must be greater than zero.")
        if records_processed < 0:
            raise InvalidInputError("Records processed must not be negative.")

        if scope is IngestionScope.COMPANY:
            if company_id is None or security_id is not None:
                raise InvalidInputError(
                    "Company-scoped lineage requires company_id only."
                )
        elif scope is IngestionScope.SECURITY:
            if security_id is None or company_id is not None:
                raise InvalidInputError(
                    "Security-scoped lineage requires security_id only."
                )
        else:
            raise InvalidInputError("Unsupported ingestion lineage scope.")

        normalized_source = None
        if source is not None:
            try:
                normalized_source = DataSource(source)
            except ValueError as exc:
                raise InvalidInputError(
                    f"Unsupported ingestion lineage source: {source}."
                ) from exc

        return self.repository.record_success(
            ingestion_run_id=ingestion_run_id,
            dataset=dataset,
            scope=scope,
            company_id=company_id,
            security_id=security_id,
            source=normalized_source,
            source_reference=source_reference,
            records_processed=records_processed,
            recorded_at=recorded_at or datetime.now(timezone.utc),
        )

    def for_run(self, ingestion_run_id: int) -> tuple[IngestionLineage, ...]:
        if ingestion_run_id <= 0:
            raise InvalidInputError("Ingestion run id must be greater than zero.")
        return tuple(self.repository.list_for_run(ingestion_run_id))

    def for_entity(
        self,
        dataset: IngestionDataset,
        scope: IngestionScope,
        *,
        company_id: int | None = None,
        security_id: int | None = None,
    ) -> tuple[IngestionLineage, ...]:
        if scope is IngestionScope.COMPANY and (
            company_id is None or security_id is not None
        ):
            raise InvalidInputError("Company lineage requires company_id only.")
        if scope is IngestionScope.SECURITY and (
            security_id is None or company_id is not None
        ):
            raise InvalidInputError("Security lineage requires security_id only.")
        return tuple(
            self.repository.list_for_entity(
                dataset,
                scope,
                company_id=company_id,
                security_id=security_id,
            )
        )
