import hashlib
import json
from datetime import datetime, timezone
from typing import Mapping

from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError
from quantcore.repositories.research_observation_repository import (
    ResearchObservationRepository,
)


class ResearchObservationService:
    """Validate and persist immutable PIT-bound research observations."""

    def __init__(self, db: Session):
        self.db = db
        self.observation_repo = ResearchObservationRepository(db)

    @staticmethod
    def _normalize_as_of(as_of: datetime) -> datetime:
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        if as_of > datetime.now(timezone.utc):
            raise InvalidInputError("As-of timestamp must not be in the future.")
        return as_of

    @staticmethod
    def _normalize_manifest(input_manifest: Mapping) -> dict:
        if not isinstance(input_manifest, Mapping):
            raise InvalidInputError("Input manifest must be a mapping.")
        try:
            normalized = json.loads(
                json.dumps(
                    dict(input_manifest),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        except (TypeError, ValueError) as exc:
            raise InvalidInputError("Input manifest must be JSON serializable.") from exc
        return normalized

    @staticmethod
    def _fingerprint(manifest: Mapping) -> str:
        payload = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _validate_identity(observation_key: str, definition_version: str) -> tuple[str, str]:
        normalized_key = observation_key.strip()
        normalized_version = definition_version.strip()
        if not normalized_key:
            raise InvalidInputError("Observation key must not be empty.")
        if not normalized_version:
            raise InvalidInputError("Definition version must not be empty.")
        return normalized_key, normalized_version

    @staticmethod
    def _validate_value(value_numeric: float | None, value_text: str | None) -> None:
        if value_numeric is None and value_text is None:
            raise InvalidInputError("A research observation must have a value.")
        if value_numeric is not None and value_text is not None:
            raise InvalidInputError(
                "A research observation must use either a numeric or text value."
            )

    def create_observation(
        self,
        *,
        security_id: int,
        as_of: datetime,
        observation_key: str,
        definition_version: str,
        input_manifest: Mapping,
        value_numeric: float | None = None,
        value_text: str | None = None,
        unit: str | None = None,
    ):
        as_of = self._normalize_as_of(as_of)
        observation_key, definition_version = self._validate_identity(
            observation_key,
            definition_version,
        )
        self._validate_value(value_numeric, value_text)
        manifest = self._normalize_manifest(input_manifest)
        fingerprint = self._fingerprint(manifest)

        existing = self.observation_repo.get_by_identity(
            security_id=security_id,
            as_of=as_of,
            observation_key=observation_key,
            definition_version=definition_version,
        )
        if existing is not None:
            if (
                existing.input_fingerprint != fingerprint
                or existing.value_numeric != value_numeric
                or existing.value_text != value_text
                or existing.unit != unit
            ):
                raise InvalidInputError(
                    "Research observation identity already exists with different content."
                )
            return existing

        return self.observation_repo.create(
            security_id=security_id,
            as_of=as_of,
            observation_key=observation_key,
            definition_version=definition_version,
            value_numeric=value_numeric,
            value_text=value_text,
            unit=unit,
            input_manifest=manifest,
            input_fingerprint=fingerprint,
            created_at=datetime.now(timezone.utc),
        )

    def get_for_security_as_of(
        self,
        *,
        security_id: int,
        as_of: datetime,
    ):
        return self.observation_repo.get_for_security_as_of(
            security_id,
            self._normalize_as_of(as_of),
        )
