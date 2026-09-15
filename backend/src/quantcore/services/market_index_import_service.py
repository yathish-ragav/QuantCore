from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json

from quantcore.core.exceptions import DataValidationError, InvalidInputError
from quantcore.models.market_index_load import MarketIndexDataLoadStatus
from quantcore.repositories.market_index_load_repository import MarketIndexDataLoadRepository
from quantcore.services.market_index_service import IndexConstituentInput, MarketIndexService
from quantcore.services.market_index_source_service import MarketIndexDataSourceService


@dataclass(frozen=True)
class IndexMembershipImportRow:
    """Canonical row produced by an authorized index-source mapping stage."""

    security_id: int
    effective_from: date
    effective_to: date | None
    weight: Decimal | None
    known_at: datetime
    source_reference: str | None = None


class MarketIndexImportService:
    """Persist authorized historical index membership snapshots append-only."""

    def __init__(self, db):
        self.db = db
        self.index_service = MarketIndexService(db)
        self.source_service = MarketIndexDataSourceService(db)
        self.load_repository = MarketIndexDataLoadRepository(db)

    @staticmethod
    def _fingerprint(rows: tuple[IndexMembershipImportRow, ...]) -> str:
        canonical = [
            {
                "security_id": row.security_id,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat() if row.effective_to else None,
                "weight": str(row.weight) if row.weight is not None else None,
                "known_at": row.known_at.isoformat(),
                "source_reference": row.source_reference,
            }
            for row in sorted(
                rows,
                key=lambda item: (
                    item.security_id,
                    item.effective_from,
                    item.effective_to or date.max,
                    item.known_at,
                    item.source_reference or "",
                ),
            )
        ]
        return sha256(
            json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()

    def import_rows(
        self,
        *,
        index_key: str,
        source_key: str,
        rows: list[IndexMembershipImportRow] | tuple[IndexMembershipImportRow, ...],
        observed_at: datetime | None = None,
    ) -> int:
        normalized = tuple(rows)
        if not normalized:
            raise InvalidInputError("At least one index membership row is required.")

        source = self.source_service.require_storage_authorized(source_key)
        index = self.index_service.get(index_key)
        if index.data_source_id != source.id:
            raise DataValidationError(
                f"Index '{index.key}' is not configured to use data source '{source.key}'."
            )

        fingerprint = self._fingerprint(normalized)
        existing = self.load_repository.get_by_fingerprint(
            index.id, source.id, fingerprint
        )
        if existing is not None:
            status = MarketIndexDataLoadStatus(existing.status)
            if status is MarketIndexDataLoadStatus.COMPLETED:
                return existing.records_imported
            raise DataValidationError(
                f"Index data load with fingerprint {fingerprint} already exists with status {status.value}."
            )

        load = self.load_repository.create(
            index_id=index.id,
            data_source_id=source.id,
            fingerprint=fingerprint,
            status=MarketIndexDataLoadStatus.RUNNING.value,
            records_received=len(normalized),
            records_imported=0,
            started_at=observed_at or datetime.now(timezone.utc),
        )
        self.db.flush()

        try:
            imported = self.index_service.add_constituents(
                index.key,
                [
                    IndexConstituentInput(
                        security_id=row.security_id,
                        effective_from=row.effective_from,
                        effective_to=row.effective_to,
                        weight=row.weight,
                        source_reference=row.source_reference,
                        known_at=row.known_at,
                    )
                    for row in normalized
                ],
                observed_at=observed_at,
            )
            load.status = MarketIndexDataLoadStatus.COMPLETED.value
            load.records_imported = imported
            load.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            return imported
        except Exception as exc:
            self.db.rollback()
            failed = self.load_repository.get_by_fingerprint(
                index.id, source.id, fingerprint
            )
            if failed is not None:
                failed.status = MarketIndexDataLoadStatus.FAILED.value
                failed.error_message = str(exc)[:4000]
                failed.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            raise
