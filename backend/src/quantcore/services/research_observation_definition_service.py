from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Protocol

from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.pit_alignment_service import PITAlignedSnapshot, PITAlignmentService
from quantcore.services.research_observation_service import ResearchObservationService


@dataclass(frozen=True)
class ResearchObservationValue:
    """Value produced by a versioned research-observation definition."""

    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    input_manifest: Mapping | None = None


class ResearchObservationDefinition(Protocol):
    """Contract for deterministic research calculations over a PIT snapshot."""

    @property
    def observation_key(self) -> str: ...

    @property
    def definition_version(self) -> str: ...

    def compute(self, snapshot: PITAlignedSnapshot) -> ResearchObservationValue: ...


class ResearchObservationDefinitionRegistry:
    """Resolve versioned observation definitions without persisting definitions."""

    def __init__(self, definitions: Iterable[ResearchObservationDefinition] = ()):
        self._definitions: dict[tuple[str, str], ResearchObservationDefinition] = {}
        for definition in definitions:
            self.register(definition)

    @staticmethod
    def _identity(definition: ResearchObservationDefinition) -> tuple[str, str]:
        key = definition.observation_key.strip()
        version = definition.definition_version.strip()
        if not key:
            raise InvalidInputError("Observation key must not be empty.")
        if not version:
            raise InvalidInputError("Definition version must not be empty.")
        return key, version

    def register(self, definition: ResearchObservationDefinition) -> None:
        identity = self._identity(definition)
        if identity in self._definitions:
            raise InvalidInputError(
                "Research observation definition identity is already registered."
            )
        self._definitions[identity] = definition

    def get(
        self,
        observation_key: str,
        definition_version: str,
    ) -> ResearchObservationDefinition:
        key = observation_key.strip()
        version = definition_version.strip()
        if not key:
            raise InvalidInputError("Observation key must not be empty.")
        if not version:
            raise InvalidInputError("Definition version must not be empty.")
        definition = self._definitions.get((key, version))
        if definition is None:
            raise ResourceNotFoundError(
                f"Research observation definition not found: {key} v{version}"
            )
        return definition


class ResearchObservationDefinitionService:
    """Compute and persist versioned research observations from one PIT snapshot."""

    def __init__(
        self,
        db: Session,
        definitions: Iterable[ResearchObservationDefinition] = (),
    ):
        self.db = db
        self.pit_alignment_service = PITAlignmentService(db)
        self.observation_service = ResearchObservationService(db)
        self.definition_registry = ResearchObservationDefinitionRegistry(definitions)

    @staticmethod
    def _normalize_as_of(as_of: datetime) -> datetime:
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        if as_of > datetime.now(timezone.utc):
            raise InvalidInputError("As-of timestamp must not be in the future.")
        return as_of

    @staticmethod
    def _normalize_manifest(manifest: Mapping) -> dict:
        if not isinstance(manifest, Mapping):
            raise InvalidInputError("Definition input manifest must be a mapping.")
        return dict(manifest)

    @staticmethod
    def _validate_result(result: ResearchObservationValue) -> None:
        if not isinstance(result, ResearchObservationValue):
            raise InvalidInputError(
                "Research observation definitions must return ResearchObservationValue."
            )
        if result.value_numeric is None and result.value_text is None:
            raise InvalidInputError("A research observation definition must produce a value.")
        if result.value_numeric is not None and result.value_text is not None:
            raise InvalidInputError(
                "A research observation definition must produce either a numeric or text value."
            )

    def compute_observation(
        self,
        symbol: str,
        *,
        as_of: datetime,
        observation_key: str,
        definition_version: str,
        macro_series_ids: Iterable[str] = (),
    ):
        """Compute one definition from one aligned PIT snapshot and persist it."""
        as_of = self._normalize_as_of(as_of)
        definition = self.definition_registry.get(
            observation_key,
            definition_version,
        )

        snapshot = self.pit_alignment_service.get_snapshot(
            symbol,
            as_of=as_of,
            macro_series_ids=tuple(macro_series_ids),
        )
        result = definition.compute(snapshot)
        self._validate_result(result)

        input_manifest = {
            "definition": {
                "observation_key": definition.observation_key.strip(),
                "definition_version": definition.definition_version.strip(),
            },
            "pit_snapshot": {
                "symbol": snapshot.symbol,
                "security_id": snapshot.security_id,
                "company_id": snapshot.company_id,
                "as_of": snapshot.as_of.isoformat(),
            },
            "inputs": self._normalize_manifest(result.input_manifest or {}),
        }

        return self.observation_service.create_observation(
            security_id=snapshot.security_id,
            as_of=snapshot.as_of,
            observation_key=definition.observation_key,
            definition_version=definition.definition_version,
            value_numeric=result.value_numeric,
            value_text=result.value_text,
            unit=result.unit,
            input_manifest=input_manifest,
        )
