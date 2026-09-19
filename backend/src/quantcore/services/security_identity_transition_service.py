from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from quantcore.core.enums import CorporateActionType
from quantcore.core.exceptions import DataValidationError, ResourceNotFoundError
from quantcore.models.corporate_action_revision import CorporateActionRevision
from quantcore.models.provenance import DataSource
from quantcore.repositories.security_identifier_history_repository import (
    SecurityIdentifierHistoryRepository,
)
from quantcore.repositories.security_repository import SecurityRepository


@dataclass(frozen=True)
class SecurityIdentityTransitionResult:
    """Result of applying an authoritative security-identity transition."""

    security_id: int
    effective_date: date
    old_symbol: str
    old_exchange: str
    new_symbol: str
    new_exchange: str
    applied: bool


class SecurityIdentityTransitionService:
    """Apply authoritative, effective-dated security identity transitions.

    This service deliberately does not infer transitions from ticker similarity,
    CIK equality, or provider snapshots.  Callers must provide an immutable
    CorporateActionRevision containing the authoritative transition evidence.

    The service does not commit the database transaction.  The caller owns the
    transaction so the identity transition can be committed atomically with the
    authoritative event that caused it to be applied.
    """

    _SUPPORTED_ACTIONS = frozenset(
        {
            CorporateActionType.TICKER_CHANGE,
            CorporateActionType.EXCHANGE_CHANGE,
        }
    )

    def __init__(self, db):
        self.db = db
        self.security_repo = SecurityRepository(db)
        self.identifier_history_repo = SecurityIdentifierHistoryRepository(db)

    def apply_revision(
        self,
        revision: CorporateActionRevision,
        *,
        as_of: datetime | None = None,
    ) -> SecurityIdentityTransitionResult:
        if revision.action_type not in self._SUPPORTED_ACTIONS:
            raise DataValidationError(
                "Security identity transitions only support TICKER_CHANGE "
                "and EXCHANGE_CHANGE corporate actions."
            )

        if revision.source is None:
            raise DataValidationError(
                "Security identity transition requires authoritative source provenance."
            )
        if revision.source is not DataSource.SEC:
            raise DataValidationError(
                "Security identity transitions currently require SEC provenance."
            )
        if not revision.source_reference:
            raise DataValidationError(
                "Security identity transition requires a source reference."
            )
        if revision.known_at.tzinfo is None:
            raise DataValidationError("Security identity transition known_at must be timezone-aware.")

        now = as_of or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise DataValidationError("Transition as_of must be timezone-aware.")
        if revision.effective_date > now.date():
            raise DataValidationError(
                "Cannot apply a future security identity transition to the current security identity."
            )
        if revision.known_at > now:
            raise DataValidationError(
                "Cannot apply a transition that was not yet known at the requested as_of time."
            )

        # CorporateActionRevision.security_id is the canonical foreign key.
        security = self.security_repo.get_by_id(revision.security_id)
        if security is None:
            raise ResourceNotFoundError(
                f"Security '{revision.security_id}' not found for identity transition."
            )

        old_symbol = revision.old_symbol or security.symbol
        old_exchange = revision.old_exchange or security.exchange
        new_symbol = revision.new_symbol or security.symbol
        new_exchange = revision.new_exchange or security.exchange

        if revision.action_type is CorporateActionType.TICKER_CHANGE:
            if not revision.old_symbol or not revision.new_symbol:
                raise DataValidationError(
                    "TICKER_CHANGE requires old_symbol and new_symbol."
                )
            if revision.old_exchange and revision.old_exchange != security.exchange:
                raise DataValidationError(
                    "TICKER_CHANGE old_exchange does not match the current security identity."
                )
            if revision.new_exchange and revision.new_exchange != security.exchange:
                raise DataValidationError(
                    "TICKER_CHANGE cannot change exchange; use EXCHANGE_CHANGE."
                )
            old_exchange = security.exchange
            new_exchange = security.exchange
        else:
            if not revision.old_exchange or not revision.new_exchange:
                raise DataValidationError(
                    "EXCHANGE_CHANGE requires old_exchange and new_exchange."
                )
            if revision.old_symbol and revision.old_symbol != security.symbol:
                raise DataValidationError(
                    "EXCHANGE_CHANGE old_symbol does not match the current security identity."
                )
            if revision.new_symbol and revision.new_symbol != security.symbol:
                raise DataValidationError(
                    "EXCHANGE_CHANGE cannot change ticker; use TICKER_CHANGE."
                )
            old_symbol = security.symbol
            new_symbol = security.symbol

        if old_symbol == new_symbol and old_exchange == new_exchange:
            raise DataValidationError("Security identity transition does not change identity.")

        target = self.identifier_history_repo.get_current(
            security.id,
            new_symbol,
            new_exchange,
        )
        if target is not None:
            if (
                target.effective_from == revision.effective_date
                and target.known_at == revision.known_at
            ):
                return SecurityIdentityTransitionResult(
                    security_id=security.id,
                    effective_date=revision.effective_date,
                    old_symbol=old_symbol,
                    old_exchange=old_exchange,
                    new_symbol=new_symbol,
                    new_exchange=new_exchange,
                    applied=False,
                )
            raise DataValidationError(
                "Target identifier already exists with incompatible transition metadata."
            )

        if old_symbol != security.symbol or old_exchange != security.exchange:
            raise DataValidationError(
                "Security identity transition is stale: its old identity does not "
                "match the security's current identity."
            )

        current = self.identifier_history_repo.get_current(
            security.id,
            old_symbol,
            old_exchange,
        )
        if current is None:
            raise DataValidationError(
                "Security identity transition requires a current identifier-history "
                "row matching the old security identity."
            )
        if revision.effective_date <= current.effective_from:
            raise DataValidationError(
                "Transition effective_date must be after the current identifier's effective_from."
            )

        conflicting = self.security_repo.get_by_company_symbol_exchange(
            security.company_id,
            new_symbol,
            new_exchange,
        )
        if conflicting is not None and conflicting.id != security.id:
            raise DataValidationError(
                "Target security identity is already owned by another Security; "
                "identity transitions never merge securities implicitly."
            )

        self.identifier_history_repo.close_current(
            security.id,
            old_symbol,
            old_exchange,
            effective_to=revision.effective_date,
        )

        from quantcore.models.security_identifier_history import SecurityIdentifierHistory

        self.db.add(
            SecurityIdentifierHistory(
                security_id=security.id,
                symbol=new_symbol,
                exchange=new_exchange,
                effective_from=revision.effective_date,
                effective_to=None,
                known_at=revision.known_at,
                source=revision.source.value if hasattr(revision.source, "value") else str(revision.source),
                source_reference=revision.source_reference,
                first_seen_at=revision.known_at,
                last_seen_at=revision.known_at,
                is_current=True,
            )
        )

        security.symbol = new_symbol
        security.exchange = new_exchange

        return SecurityIdentityTransitionResult(
            security_id=security.id,
            effective_date=revision.effective_date,
            old_symbol=old_symbol,
            old_exchange=old_exchange,
            new_symbol=new_symbol,
            new_exchange=new_exchange,
            applied=True,
        )
