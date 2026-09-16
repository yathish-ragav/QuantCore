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
            and existing.related_security_id == data.related_security_id
            and existing.old_symbol == data.old_symbol
            and existing.new_symbol == data.new_symbol
            and existing.old_exchange == data.old_exchange
            and existing.new_exchange == data.new_exchange
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
            related_security_id=action.related_security_id,
            old_symbol=action.old_symbol,
            new_symbol=action.new_symbol,
            old_exchange=action.old_exchange,
            new_exchange=action.new_exchange,
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

            normalized_actions: list[CorporateActionData] = []
            seen_identities: set[tuple[object, object]] = set()
            seen_references: set[str] = set()
            for action in raw_actions:
                if not isinstance(action, CorporateActionData):
                    raise DataValidationError(
                        "Market-data provider returned an invalid corporate action."
                    )

                identity = (action.effective_date, action.action_type)
                if identity in seen_identities:
                    raise DataValidationError(
                        "Market-data provider returned duplicate corporate-action "
                        f"identity for '{symbol}': {action.effective_date} / "
                        f"{action.action_type.value}."
                    )
                seen_identities.add(identity)

                if action.source_reference:
                    if action.source_reference in seen_references:
                        raise DataValidationError(
                            "Market-data provider returned duplicate corporate-action "
                            f"source reference for '{symbol}': {action.source_reference}."
                        )
                    seen_references.add(action.source_reference)

                normalized_actions.append(action)

            source = DataSource(self.client.SOURCE)
            fetched_at = datetime.now(timezone.utc)
            existing_actions = {
                (existing.effective_date, existing.action_type): existing
                for existing in self.action_repo.get_for_security(security.id)
            }

            created = 0
            updated = 0
            unchanged = 0
            revisions: list[tuple[object, int]] = []
            new_actions: list[tuple[CorporateActionData, object]] = []

            for action in normalized_actions:
                existing = existing_actions.get(
                    (action.effective_date, action.action_type)
                )

                if existing is not None:
                    if self._matches(existing, action):
                        unchanged += 1
                        if existing.source != source:
                            existing.source = source
                        existing.fetched_at = fetched_at
                        if action.source_reference:
                            existing.source_reference = action.source_reference
                        continue

                    existing.amount = action.amount
                    existing.split_ratio = action.split_ratio
                    existing.related_security_id = action.related_security_id
                    existing.old_symbol = action.old_symbol
                    existing.new_symbol = action.new_symbol
                    existing.old_exchange = action.old_exchange
                    existing.new_exchange = action.new_exchange
                    existing.source = source
                    existing.fetched_at = fetched_at
                    if action.source_reference:
                        existing.source_reference = action.source_reference
                    updated += 1
                    revisions.append((existing, 0))
                    continue

                created_action = self.action_repo.create(
                    security_id=security.id,
                    effective_date=action.effective_date,
                    action_type=action.action_type,
                    amount=action.amount,
                    split_ratio=action.split_ratio,
                    related_security_id=action.related_security_id,
                    old_symbol=action.old_symbol,
                    new_symbol=action.new_symbol,
                    old_exchange=action.old_exchange,
                    new_exchange=action.new_exchange,
                    source=source,
                    fetched_at=fetched_at,
                    source_reference=action.source_reference,
                )
                created += 1
                new_actions.append((action, created_action))

            # Flush all new actions together so generated primary keys are
            # available before creating their immutable revision snapshots.
            if new_actions:
                self.db.flush()

            for action, created_action in new_actions:
                self._create_revision(
                    created_action,
                    source=source,
                    known_at=fetched_at,
                    revision_number=1,
                )

            # Resolve all changed-action revision numbers with one grouped query.
            changed_actions = [action for action, _ in revisions]
            next_revision_numbers = self.revision_repo.get_next_revision_numbers(
                [action.id for action in changed_actions]
            )
            for action, _ in revisions:
                self._create_revision(
                    action,
                    source=source,
                    known_at=fetched_at,
                    revision_number=next_revision_numbers[action.id],
                )

            self.db.commit()
            return CorporateActionSyncResult(
                created=created,
                updated=updated,
                unchanged=unchanged,
                records_processed=len(normalized_actions),
            )
        except Exception:
            self.db.rollback()
            raise
