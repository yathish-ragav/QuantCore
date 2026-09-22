from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from quantcore.core.exceptions import DataValidationError, InvalidInputError, ResourceNotFoundError
from quantcore.models.security import Security
from quantcore.models.security_identifier_history import SecurityIdentifierHistory
from quantcore.repositories.security_identifier_history_repository import (
    SecurityIdentifierHistoryRepository,
)


@dataclass(frozen=True)
class ResolvedSecurityListing:
    """Security resolved through its effective-dated ticker/exchange identity."""

    security: Security
    history: SecurityIdentifierHistory


class SecurityListingIdentityService:
    """Resolve ticker/exchange identifiers under a PIT effective/knowledge boundary.

    A ticker is an identifier, not the canonical security identity. Historical
    callers must resolve it through ``security_identifier_history`` before
    reading security observations. This service intentionally has no fallback
    to today's ``Security.symbol`` when a PIT boundary is supplied: doing so
    would allow a current identifier to leak into historical research.
    """

    def __init__(self, db):
        self.db = db
        self.repository = SecurityIdentifierHistoryRepository(db)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise InvalidInputError("Symbol must not be empty.")
        return normalized

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def resolve_as_of(
        self,
        symbol: str,
        *,
        effective_on: date,
        known_at: datetime,
        exchange: str | None = None,
    ) -> ResolvedSecurityListing:
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_exchange = exchange.strip().upper() if exchange else None
        if normalized_exchange == "":
            raise InvalidInputError("Exchange must not be empty when supplied.")
        normalized_known_at = self._normalize_timestamp(known_at)

        rows = self.repository.resolve_as_of(
            normalized_symbol,
            effective_on=effective_on,
            known_at=normalized_known_at,
            exchange=normalized_exchange,
        )
        if not rows:
            exchange_text = f" on {normalized_exchange}" if normalized_exchange else ""
            raise ResourceNotFoundError(
                f"No security listing found for '{normalized_symbol}'{exchange_text} "
                f"at effective date {effective_on} known by {normalized_known_at.isoformat()}."
            )
        if len(rows) > 1:
            exchanges = ", ".join(sorted({row.exchange for row in rows}))
            raise DataValidationError(
                f"Security symbol '{normalized_symbol}' is ambiguous at the requested "
                f"point-in-time across exchanges: {exchanges}."
            )

        history = rows[0]
        security = self.db.get(Security, history.security_id)
        if security is None:
            raise ResourceNotFoundError(
                f"Security '{history.security_id}' referenced by listing history was not found."
            )
        return ResolvedSecurityListing(security=security, history=history)

    def resolve_security_as_of(
        self,
        symbol: str,
        *,
        as_of: datetime,
        exchange: str | None = None,
    ) -> Security:
        """Resolve a security from its listing identity at one PIT timestamp."""
        normalized_as_of = self._normalize_timestamp(as_of)
        if normalized_as_of > datetime.now(timezone.utc):
            raise InvalidInputError("As-of timestamp must not be in the future.")
        return self.resolve_as_of(
            symbol,
            effective_on=normalized_as_of.date(),
            known_at=normalized_as_of,
            exchange=exchange,
        ).security

    def resolve_company_as_of(
        self,
        symbol: str,
        *,
        as_of: datetime,
        exchange: str | None = None,
    ):
        """Resolve the issuer behind a historical ticker/exchange identity."""
        security = self.resolve_security_as_of(
            symbol,
            as_of=as_of,
            exchange=exchange,
        )
        company = security.company
        if company is None:
            raise ResourceNotFoundError(
                f"Security '{symbol.strip().upper()}' has no company identity."
            )
        return company
