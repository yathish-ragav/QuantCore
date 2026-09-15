from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantcore.core.exceptions import DataValidationError, InvalidInputError, ResourceNotFoundError
from quantcore.models.market_index import MarketIndex
from quantcore.models.security import Security
from quantcore.repositories.market_index_repository import MarketIndexRepository


@dataclass(frozen=True)
class IndexConstituentInput:
    """Normalized membership interval supplied by an authorized index data source."""

    security_id: int
    effective_from: date
    effective_to: date | None = None
    weight: Decimal | None = None
    source_reference: str | None = None
    known_at: datetime | None = None


@dataclass(frozen=True)
class ResearchUniverseSnapshot:
    """Deterministic point-in-time security universe resolved from an index."""

    index_key: str
    as_of: date
    security_ids: tuple[int, ...]
    fingerprint: str

    @property
    def size(self) -> int:
        return len(self.security_ids)


class MarketIndexService:
    """Own market-index identity and point-in-time constituent resolution."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = MarketIndexRepository(db)

    @staticmethod
    def _normalize_key(key: str) -> str:
        normalized = key.strip().upper()
        if not normalized:
            raise InvalidInputError("Index key must not be empty.")
        return normalized

    @staticmethod
    def _normalize_as_of(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise InvalidInputError("Index as-of value must be a datetime.")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        if value > datetime.now(timezone.utc):
            raise InvalidInputError("Index as-of value must not be in the future.")
        return value

    @staticmethod
    def _normalize_input(item: IndexConstituentInput) -> IndexConstituentInput:
        if not isinstance(item, IndexConstituentInput):
            raise InvalidInputError("Index constituents must use IndexConstituentInput.")
        if item.security_id <= 0:
            raise InvalidInputError("Security ID must be positive.")
        if item.effective_to is not None and item.effective_to <= item.effective_from:
            raise InvalidInputError("effective_to must be later than effective_from.")
        if item.weight is not None and item.weight < 0:
            raise InvalidInputError("Index constituent weight must not be negative.")
        if item.known_at is None:
            raise InvalidInputError(
                "Index constituent known_at is required for point-in-time resolution."
            )
        known_at = item.known_at
        if known_at.tzinfo is None:
            known_at = known_at.replace(tzinfo=timezone.utc)
        return IndexConstituentInput(
            security_id=item.security_id,
            effective_from=item.effective_from,
            effective_to=item.effective_to,
            weight=item.weight,
            source_reference=item.source_reference,
            known_at=known_at,
        )

    def get(self, key: str) -> MarketIndex:
        normalized = self._normalize_key(key)
        index = self.repository.get_by_key(normalized)
        if index is None or not index.is_active:
            raise ResourceNotFoundError(f"Market index '{normalized}' not found.")
        return index

    def list_active(self) -> list[MarketIndex]:
        return self.repository.list_active()

    def create(
        self,
        *,
        key: str,
        name: str,
        provider: str,
        methodology_reference: str | None = None,
        source_reference: str | None = None,
        data_source_id: int | None = None,
    ) -> MarketIndex:
        normalized_key = self._normalize_key(key)
        name = name.strip()
        provider = provider.strip()
        if not name:
            raise InvalidInputError("Index name must not be empty.")
        if not provider:
            raise InvalidInputError("Index provider must not be empty.")
        if self.repository.get_by_key(normalized_key) is not None:
            raise DataValidationError(
                f"Market index '{normalized_key}' already exists."
            )
        index = self.repository.create(
            key=normalized_key,
            name=name,
            provider=provider,
            methodology_reference=methodology_reference,
            source_reference=source_reference,
            data_source_id=data_source_id,
        )
        self.db.flush()
        return index

    def add_constituents(
        self,
        key: str,
        constituents: Iterable[IndexConstituentInput],
        *,
        observed_at: datetime | None = None,
    ) -> int:
        index = self.get(key)
        items = tuple(self._normalize_input(item) for item in constituents)
        if not items:
            raise InvalidInputError("At least one index constituent is required.")

        observed_at = observed_at or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)

        security_ids = {item.security_id for item in items}
        # Load concrete security rows so historical members can be inactive
        # while still remaining valid index constituents.
        existing_security_ids = set(
            self.db.scalars(
                select(Security.id).where(Security.id.in_(security_ids))
            ).all()
        )
        missing_security_ids = security_ids - existing_security_ids
        if missing_security_ids:
            raise ResourceNotFoundError(
                "Index constituent securities not found: "
                + ", ".join(str(value) for value in sorted(missing_security_ids))
            )

        seen_starts: set[tuple[int, date]] = set()
        accepted: list[IndexConstituentInput] = []
        for item in items:
            identity = (item.security_id, item.effective_from)
            if identity in seen_starts:
                raise DataValidationError(
                    "Index constituents contain duplicate membership starts."
                )
            seen_starts.add(identity)

            existing = self.repository.get_constituents_for_security(
                index.id,
                item.security_id,
            )
            for previous in existing:
                if (
                    previous.effective_from == item.effective_from
                    and previous.known_at == item.known_at
                ):
                    raise DataValidationError(
                        "An index membership revision already exists for this security, effective date, and knowledge timestamp."
                    )
                if (
                    previous.known_at == item.known_at
                    and self._intervals_overlap(
                        previous.effective_from,
                        previous.effective_to,
                        item.effective_from,
                        item.effective_to,
                    )
                ):
                    raise DataValidationError(
                        f"Index membership intervals overlap for security {item.security_id}."
                    )
            for previous in accepted:
                if previous.security_id == item.security_id and self._intervals_overlap(
                    previous.effective_from,
                    previous.effective_to,
                    item.effective_from,
                    item.effective_to,
                ):
                    raise DataValidationError(
                        f"Index membership intervals overlap for security {item.security_id}."
                    )
            accepted.append(item)

        for item in items:
            self.repository.create_constituent(
                index_id=index.id,
                security_id=item.security_id,
                effective_from=item.effective_from,
                effective_to=item.effective_to,
                weight=item.weight,
                source_reference=item.source_reference,
                data_source_id=index.data_source_id,
                known_at=item.known_at,
                observed_at=observed_at,
            )
        self.db.flush()
        return len(items)

    @staticmethod
    def _intervals_overlap(
        first_from: date,
        first_to: date | None,
        second_from: date,
        second_to: date | None,
    ) -> bool:
        first_end = first_to or date.max
        second_end = second_to or date.max
        return first_from < second_end and second_from < first_end

    def constituents_as_of(
        self,
        key: str,
        *,
        as_of: datetime,
    ):
        index = self.get(key)
        normalized_as_of = self._normalize_as_of(as_of)
        return self.repository.get_constituents_as_of(
            index.id,
            effective_on=normalized_as_of.date(),
            known_at=normalized_as_of,
        )

    def resolve(
        self,
        key: str,
        *,
        as_of: datetime,
    ) -> ResearchUniverseSnapshot:
        index = self.get(key)
        normalized_as_of = self._normalize_as_of(as_of)
        members = self.repository.get_constituents_as_of(
            index.id,
            effective_on=normalized_as_of.date(),
            known_at=normalized_as_of,
        )
        security_ids = tuple(sorted(member.security_id for member in members))
        canonical = json.dumps(
            {
                "index_key": index.key,
                "as_of": normalized_as_of.isoformat(),
                "security_ids": security_ids,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return ResearchUniverseSnapshot(
            index_key=index.key,
            as_of=normalized_as_of,
            security_ids=security_ids,
            fingerprint=sha256(canonical.encode("utf-8")).hexdigest(),
        )
