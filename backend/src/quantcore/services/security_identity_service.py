from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import DataValidationError, InvalidInputError, ResourceNotFoundError
from quantcore.core.security_identity import SecurityIdentifierType
from quantcore.models.security_identifier import SecurityIdentifier
from quantcore.repositories.security_identifier_repository import SecurityIdentifierRepository


@dataclass(frozen=True)
class SecurityIdentifierInput:
    security_id: int
    identifier_type: SecurityIdentifierType
    value: str
    valid_from: date
    valid_to: date | None
    known_at: datetime
    source: str
    source_reference: str | None = None
    namespace: str | None = None


class SecurityIdentityService:
    """Manage durable external identifiers and historical PIT resolution."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = SecurityIdentifierRepository(db)

    @staticmethod
    def _normalize_known_at(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _normalize_identifier_type(value) -> SecurityIdentifierType:
        try:
            if isinstance(value, SecurityIdentifierType):
                return value
            return SecurityIdentifierType(str(value).upper())
        except ValueError as exc:
            raise InvalidInputError(f"Unsupported security identifier type: {value}") from exc

    def record_identifier(self, item: SecurityIdentifierInput) -> SecurityIdentifier:
        if item.security_id <= 0:
            raise InvalidInputError("Security ID must be positive.")
        value = item.value.strip().upper()
        if not value:
            raise InvalidInputError("Security identifier value must not be empty.")
        source = item.source.strip().upper()
        if not source:
            raise InvalidInputError("Security identifier source must not be empty.")
        if item.valid_to is not None and item.valid_to <= item.valid_from:
            raise InvalidInputError("valid_to must be later than valid_from.")

        # The repository lookup below intentionally uses a direct scalar query
        # through the session so this service does not assume the security is
        # active; historical securities are valid identifier targets.
        from quantcore.models.security import Security
        security = self.db.get(Security, item.security_id)
        if security is None:
            raise ResourceNotFoundError(f"Security {item.security_id} not found.")

        identifier_type = self._normalize_identifier_type(item.identifier_type)
        namespace = (item.namespace or identifier_type.value).strip().upper()
        if not namespace:
            raise InvalidInputError("Security identifier namespace must not be empty.")
        if identifier_type is SecurityIdentifierType.VENDOR and item.namespace is None:
            raise InvalidInputError("Vendor security identifiers require a namespace.")
        known_at = self._normalize_known_at(item.known_at)

        existing = self.repository.get_exact(
            item.security_id,
            identifier_type,
            namespace,
            value,
            item.valid_from,
            known_at,
        )
        if existing is not None:
            if (
                existing.valid_to != item.valid_to
                or existing.source != source
                or existing.source_reference != item.source_reference
            ):
                raise DataValidationError(
                    "A security identifier revision already exists with different metadata."
                )
            return existing

        candidates = self.repository.get_for_security(
            item.security_id,
            identifier_type,
            namespace,
        )
        for previous in candidates:
            if previous.known_at != known_at:
                continue
            previous_end = previous.valid_to or date.max
            new_end = item.valid_to or date.max
            if item.valid_from < previous_end and previous.valid_from < new_end:
                raise DataValidationError(
                    f"Identifier intervals overlap for security {item.security_id} "
                    f"and type {identifier_type.value}."
                )

        # An identifier value may not point at two securities at the same
        # knowledge boundary while their effective intervals overlap.
        resolved = self.repository.resolve_as_of(
            identifier_type,
            namespace,
            value,
            effective_on=item.valid_from,
            known_at=known_at,
        )
        if resolved is not None and resolved.security_id != item.security_id:
            raise DataValidationError(
                f"Identifier '{value}' is already mapped to security "
                f"{resolved.security_id} at the requested knowledge boundary."
            )

        identifier = self.repository.create(
            security_id=item.security_id,
            identifier_type=identifier_type.value,
            namespace=namespace,
            value=value,
            valid_from=item.valid_from,
            valid_to=item.valid_to,
            known_at=known_at,
            source=source,
            source_reference=item.source_reference,
        )
        self.db.flush()
        return identifier

    def get_for_security_as_of(
        self,
        security_id: int,
        *,
        effective_on: date,
        known_at: datetime,
    ) -> list[SecurityIdentifier]:
        return self.repository.get_for_security_as_of(
            security_id,
            effective_on=effective_on,
            known_at=self._normalize_known_at(known_at),
        )

    def resolve(
        self,
        identifier_type: SecurityIdentifierType,
        value: str,
        *,
        namespace: str | None = None,
        effective_on: date,
        known_at: datetime,
    ) -> SecurityIdentifier | None:
        normalized_value = value.strip().upper()
        if not normalized_value:
            raise InvalidInputError("Security identifier value must not be empty.")
        normalized_type = self._normalize_identifier_type(identifier_type)
        normalized_namespace = (namespace or normalized_type.value).strip().upper()
        if normalized_type is SecurityIdentifierType.VENDOR and namespace is None:
            raise InvalidInputError("Vendor security identifiers require a namespace.")
        if not normalized_namespace:
            raise InvalidInputError("Security identifier namespace must not be empty.")
        return self.repository.resolve_as_of(
            normalized_type,
            normalized_namespace,
            normalized_value,
            effective_on=effective_on,
            known_at=self._normalize_known_at(known_at),
        )
