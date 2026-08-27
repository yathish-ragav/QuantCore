from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import (
    DataValidationError,
    InvalidInputError,
    ResourceNotFoundError,
)
from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.models.provenance import DataSource
from quantcore.processing.cleaner import DataCleaner
from quantcore.repositories.corporate_action_repository import (
    CorporateActionRepository,
)
from quantcore.repositories.corporate_action_revision_repository import (
    CorporateActionRevisionRepository,
)
from quantcore.repositories.security_repository import SecurityRepository
from quantcore.schemas.corporate_action import CorporateActionData


@dataclass(frozen=True)
class CorporateActionSyncResult:
    """Reconciliation counts produced by one corporate-action sync."""

    created: int
    updated: int
    unchanged: int
    records_processed: int


class CorporateActionService:
    """Synchronize normalized corporate actions for one security."""

    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()
        self.security_repo = SecurityRepository(db)
        self.action_repo = CorporateActionRepository(db)
        self.revision_repo = CorporateActionRevisionRepository(db)

    def get_security(self, symbol: str):
        symbol = DataCleaner.clean_symbol(symbol)
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        security = self.security_repo.get_by_symbol(symbol)
        if security is None:
            raise ResourceNotFoundError(
                f"Security '{symbol}' not found. Run security sync first."
            )
        return security

    def get_actions(
        self,
        symbol: str,
        as_of: datetime | None = None,
    ):
        security = self.get_security(symbol)
        if as_of is None:
            return self.action_repo.get_for_security(security.id)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        if as_of > datetime.now(timezone.utc):
            raise InvalidInputError("As-of timestamp must not be in the future.")
        return self.revision_repo.get_latest_for_security_as_of(
            security.id,
            as_of,
        )

    @staticmethod
    def _matches(existing, data) -> bool:
        return (
            existing.effective_date == data.effective_date
            and existing.action_type == data.action_type
            and existing.amount == data.amount
            and existing.split_ratio == data.split_ratio
        )

    def _create_revision(
        self,
        action,
        *,
        source: DataSource,
        known_at: datetime,
        revision_number: int,
    ) -> None:
        self.revision_repo.create(
            action_id=action.id,
            security_id=action.security_id,
            revision_number=revision_number,
            effective_date=action.effective_date,
            action_type=action.action_type,
            amount=action.amount,
            split_ratio=action.split_ratio,
            source=source,
            known_at=known_at,
            source_reference=action.source_reference,
        )

    def sync_corporate_actions(
        self,
        symbol: str,
        period: str = "max",
    ) -> CorporateActionSyncResult:
        symbol = DataCleaner.clean_symbol(symbol)
        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        try:
            security = self.get_security(symbol)
            raw_actions = self.client.get_corporate_actions(
                symbol,
                period=period,
            )

            if not isinstance(raw_actions, list):
                raise DataValidationError(
                    f"Invalid corporate action data for '{symbol}'."
                )

            source = DataSource(self.client.SOURCE)
            fetched_at = datetime.now(timezone.utc)
            created = 0
            updated = 0
            unchanged = 0
            records_processed = 0

            for action in raw_actions:
                if not isinstance(action, CorporateActionData):
                    raise DataValidationError(
                        "Market-data provider returned an invalid corporate action."
                    )

                records_processed += 1
                existing = self.action_repo.get_by_identity(
                    security.id,
                    action.effective_date,
                    action.action_type,
                )

                if existing is not None:
                    if self._matches(existing, action):
                        unchanged += 1
                        if existing.source != source:
                            existing.source = source
                        existing.fetched_at = fetched_at
                        continue

                    next_revision = self.revision_repo.get_next_revision_number(existing.id)
                    existing.amount = action.amount
                    existing.split_ratio = action.split_ratio
                    existing.source = source
                    existing.fetched_at = fetched_at
                    existing.source_reference = (
                        f"{symbol}:{action.effective_date.isoformat()}:"
                        f"{action.action_type.value}"
                    )
                    self._create_revision(
                        existing,
                        source=source,
                        known_at=fetched_at,
                        revision_number=next_revision,
                    )
                    updated += 1
                    continue

                created_action = self.action_repo.create(
                    security_id=security.id,
                    effective_date=action.effective_date,
                    action_type=action.action_type,
                    amount=action.amount,
                    split_ratio=action.split_ratio,
                    source=source,
                    fetched_at=fetched_at,
                    source_reference=(
                        f"{symbol}:{action.effective_date.isoformat()}:"
                        f"{action.action_type.value}"
                    ),
                )
                self.db.flush()
                self._create_revision(
                    created_action,
                    source=source,
                    known_at=fetched_at,
                    revision_number=1,
                )
                created += 1

            self.db.commit()
            return CorporateActionSyncResult(
                created=created,
                updated=updated,
                unchanged=unchanged,
                records_processed=records_processed,
            )
        except Exception:
            self.db.rollback()
            raise
