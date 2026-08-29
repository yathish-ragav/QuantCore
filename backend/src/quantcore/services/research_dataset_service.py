from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_observation_service import ResearchObservationService


@dataclass(frozen=True)
class ResearchFeature:
    """One versioned research feature selected at a PIT boundary."""

    observation_key: str
    definition_version: str
    observation_as_of: datetime
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    input_fingerprint: str
    input_manifest: dict


@dataclass(frozen=True)
class ResearchFeatureVector:
    """Immutable, deterministic research feature vector for one security."""

    symbol: str
    security_id: int
    as_of: datetime
    features: tuple[ResearchFeature, ...]


class ResearchDatasetService:
    """Build read-only PIT research feature vectors from materialized observations."""

    def __init__(self, db: Session):
        self.db = db
        self.observation_service = ResearchObservationService(db)

    @staticmethod
    def _normalize_as_of(as_of: datetime) -> datetime:
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        if as_of > datetime.now(timezone.utc):
            raise InvalidInputError("As-of timestamp must not be in the future.")
        return as_of

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise InvalidInputError("Symbol must not be empty.")
        return normalized

    @staticmethod
    def _normalize_definition_identities(
        definition_identities: Iterable[tuple[str, str]],
    ) -> tuple[tuple[str, str], ...]:
        identities = tuple(definition_identities)
        if not identities:
            raise InvalidInputError("At least one definition identity is required.")

        normalized: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for identity in identities:
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
                raise InvalidInputError("Definition identities must not contain duplicates.")
            seen.add(item)
            normalized.append(item)
        return tuple(normalized)

    @staticmethod
    def _feature(observation) -> ResearchFeature:
        return ResearchFeature(
            observation_key=observation.observation_key.strip(),
            definition_version=observation.definition_version.strip(),
            observation_as_of=observation.as_of,
            value_numeric=observation.value_numeric,
            value_text=observation.value_text,
            unit=observation.unit,
            input_fingerprint=observation.input_fingerprint,
            input_manifest=observation.input_manifest,
        )

    def build_feature_vector(
        self,
        symbol: str,
        *,
        as_of: datetime,
        definition_identities: Iterable[tuple[str, str]] | None = None,
    ) -> ResearchFeatureVector:
        """Build a PIT feature vector from the latest observations known by ``as_of``.

        The vector is a read-only projection over materialized research observations.
        It does not compute or persist observations, and it never selects an
        observation whose stored ``as_of`` is after the requested boundary.
        """
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_as_of = self._normalize_as_of(as_of)

        identities = None
        if definition_identities is not None:
            identities = self._normalize_definition_identities(definition_identities)

        observations = tuple(
            self.observation_service.get_latest_for_symbol_as_of(
                normalized_symbol,
                as_of=normalized_as_of,
            )
        )
        if not observations:
            raise ResourceNotFoundError(
                f"No research observations available for '{normalized_symbol}' "
                f"as of {normalized_as_of.isoformat()}."
            )

        by_identity: dict[tuple[str, str], object] = {}
        for observation in observations:
            identity = (
                observation.observation_key.strip(),
                observation.definition_version.strip(),
            )
            if identity in by_identity:
                raise InvalidInputError(
                    "Research observations contain duplicate definition identities."
                )
            if observation.as_of > normalized_as_of:
                raise InvalidInputError(
                    "Research observation exceeds the requested as-of boundary."
                )
            by_identity[identity] = observation

        if identities is None:
            selected = tuple(
                sorted(
                    observations,
                    key=lambda item: (
                        item.observation_key.strip(),
                        item.definition_version.strip(),
                    ),
                )
            )
        else:
            missing = tuple(identity for identity in identities if identity not in by_identity)
            if missing:
                missing_text = ", ".join(
                    f"{key} v{version}" for key, version in missing
                )
                raise ResourceNotFoundError(
                    f"Research observations not materialized for '{normalized_symbol}' "
                    f"as of {normalized_as_of.isoformat()}: {missing_text}."
                )
            selected = tuple(by_identity[identity] for identity in identities)

        security_ids = {observation.security_id for observation in selected}
        if len(security_ids) != 1:
            raise InvalidInputError(
                "Research observations in a feature vector must belong to one security."
            )
        security_id = next(iter(security_ids))

        return ResearchFeatureVector(
            symbol=normalized_symbol,
            security_id=security_id,
            as_of=normalized_as_of,
            features=tuple(self._feature(observation) for observation in selected),
        )
