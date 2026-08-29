from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_dataset_service import (
    ResearchDatasetService,
    ResearchFeatureVector,
)


@dataclass(frozen=True)
class ResearchHistoricalDatasetRow:
    """One point-in-time research row for a security."""

    symbol: str
    security_id: int
    as_of: datetime
    feature_vector: ResearchFeatureVector


@dataclass(frozen=True)
class ResearchHistoricalDataset:
    """Immutable historical research panel consumed by downstream analysis."""

    rows: tuple[ResearchHistoricalDatasetRow, ...]
    definition_identities: tuple[tuple[str, str], ...] | None


class ResearchHistoricalAnalysisService:
    """Consume PIT feature vectors without computing or persisting research data."""

    def __init__(self, db: Session):
        self.db = db
        self.dataset_service = ResearchDatasetService(db)

    @staticmethod
    def _normalize_symbols(symbols: Iterable[str]) -> tuple[str, ...]:
        values = tuple(symbols)
        if not values:
            raise InvalidInputError(
                "At least one research symbol is required."
            )

        normalized: list[str] = []
        seen: set[str] = set()
        for symbol in values:
            if not isinstance(symbol, str):
                raise InvalidInputError("Research symbols must be strings.")
            item = symbol.strip().upper()
            if not item:
                raise InvalidInputError("Research symbol must not be empty.")
            if item in seen:
                raise InvalidInputError(
                    "Research symbols must not contain duplicates."
                )
            seen.add(item)
            normalized.append(item)
        return tuple(normalized)

    @staticmethod
    def _normalize_as_ofs(as_ofs: Iterable[datetime]) -> tuple[datetime, ...]:
        values = tuple(as_ofs)
        if not values:
            raise InvalidInputError(
                "At least one historical as-of timestamp is required."
            )

        now = datetime.now(timezone.utc)
        normalized: list[datetime] = []
        seen: set[datetime] = set()
        for as_of in values:
            if not isinstance(as_of, datetime):
                raise InvalidInputError("Historical as-of values must be datetimes.")
            if as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
            if as_of > now:
                raise InvalidInputError("As-of timestamp must not be in the future.")
            if as_of in seen:
                raise InvalidInputError(
                    "Historical as-of timestamps must not contain duplicates."
                )
            seen.add(as_of)
            normalized.append(as_of)
        return tuple(normalized)

    @staticmethod
    def _normalize_definition_identities(
        definition_identities: Iterable[tuple[str, str]] | None,
    ) -> tuple[tuple[str, str], ...] | None:
        if definition_identities is None:
            return None

        values = tuple(definition_identities)
        if not values:
            raise InvalidInputError("At least one definition identity is required.")

        normalized: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for identity in values:
            if not isinstance(identity, tuple) or len(identity) != 2:
                raise InvalidInputError(
                    "Definition identities must be (observation_key, definition_version) tuples."
                )
            key, version = identity
            if not isinstance(key, str) or not isinstance(version, str):
                raise InvalidInputError(
                    "Definition identities must contain string key and version values."
                )
            item = (key.strip(), version.strip())
            if not item[0]:
                raise InvalidInputError("Observation key must not be empty.")
            if not item[1]:
                raise InvalidInputError("Definition version must not be empty.")
            if item in seen:
                raise InvalidInputError(
                    "Definition identities must not contain duplicates."
                )
            seen.add(item)
            normalized.append(item)
        return tuple(normalized)

    def build_historical_dataset(
        self,
        symbols: Iterable[str],
        *,
        as_ofs: Iterable[datetime],
        definition_identities: Iterable[tuple[str, str]] | None = None,
    ) -> ResearchHistoricalDataset:
        """Build a deterministic historical panel from PIT feature-vector reads.

        The service consumes already-materialized observations through
        ``ResearchDatasetService``. It never computes, mutates, or persists
        research observations. Every requested symbol/timestamp pair must
        resolve successfully; missing data is not silently dropped.
        """
        normalized_symbols = self._normalize_symbols(symbols)
        normalized_as_ofs = self._normalize_as_ofs(as_ofs)
        normalized_identities = self._normalize_definition_identities(
            definition_identities
        )

        rows: list[ResearchHistoricalDatasetRow] = []
        for as_of in sorted(normalized_as_ofs):
            for symbol in sorted(normalized_symbols):
                vector = self.dataset_service.build_feature_vector(
                    symbol,
                    as_of=as_of,
                    definition_identities=normalized_identities,
                )
                rows.append(
                    ResearchHistoricalDatasetRow(
                        symbol=vector.symbol,
                        security_id=vector.security_id,
                        as_of=vector.as_of,
                        feature_vector=vector,
                    )
                )

        return ResearchHistoricalDataset(
            rows=tuple(rows),
            definition_identities=normalized_identities,
        )
