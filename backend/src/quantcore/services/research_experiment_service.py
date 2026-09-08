from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.models.research_experiment import (
    ResearchExperimentRun,
    ResearchExperimentRunStatus,
)
from quantcore.repositories.research_experiment_repository import ResearchExperimentRepository


DefinitionIdentity = tuple[str, str]
ResearchSignalIdentity = DefinitionIdentity
ResearchStrategyIdentity = DefinitionIdentity


class _FrozenDict(dict):
    """JSON-compatible mapping that rejects mutation after construction."""

    def __setitem__(self, key, value):
        raise TypeError("Frozen mapping cannot be modified.")

    def __delitem__(self, key):
        raise TypeError("Frozen mapping cannot be modified.")

    def clear(self):
        raise TypeError("Frozen mapping cannot be modified.")

    def pop(self, key, default=None):
        raise TypeError("Frozen mapping cannot be modified.")

    def popitem(self):
        raise TypeError("Frozen mapping cannot be modified.")

    def setdefault(self, key, default=None):
        raise TypeError("Frozen mapping cannot be modified.")

    def update(self, *args, **kwargs):
        raise TypeError("Frozen mapping cannot be modified.")

    def __ior__(self, other):
        raise TypeError("Frozen mapping cannot be modified.")


class _FrozenList(list):
    """JSON-compatible sequence that rejects mutation after construction."""

    def __setitem__(self, index, value):
        raise TypeError("Frozen sequence cannot be modified.")

    def __delitem__(self, index):
        raise TypeError("Frozen sequence cannot be modified.")

    def append(self, value):
        raise TypeError("Frozen sequence cannot be modified.")

    def clear(self):
        raise TypeError("Frozen sequence cannot be modified.")

    def extend(self, values):
        raise TypeError("Frozen sequence cannot be modified.")

    def insert(self, index, value):
        raise TypeError("Frozen sequence cannot be modified.")

    def pop(self, index=-1):
        raise TypeError("Frozen sequence cannot be modified.")

    def remove(self, value):
        raise TypeError("Frozen sequence cannot be modified.")

    def reverse(self):
        raise TypeError("Frozen sequence cannot be modified.")

    def sort(self, *args, **kwargs):
        raise TypeError("Frozen sequence cannot be modified.")

    def __iadd__(self, values):
        raise TypeError("Frozen sequence cannot be modified.")

    def __imul__(self, value):
        raise TypeError("Frozen sequence cannot be modified.")


@dataclass(frozen=True)
class ResearchExperimentDefinition:
    """Immutable, versioned contract describing one reproducible research experiment.

    The definition records the identities of every versioned research input that
    the experiment consumes. It intentionally contains no execution state,
    results, artifacts, portfolio holdings, or orchestration behavior.
    """

    experiment_key: str
    definition_version: str
    dataset_identity: DefinitionIdentity
    universe_identity: DefinitionIdentity
    observation_as_of: datetime
    factor_identities: tuple[DefinitionIdentity, ...] = ()
    signal_identity: ResearchSignalIdentity | None = None
    strategy_identity: ResearchStrategyIdentity | None = None
    parameters: Mapping[str, Any] | None = None
    code_version: str = ""

    def __post_init__(self) -> None:
        experiment_key = self._required_text(self.experiment_key, "Experiment key")
        definition_version = self._required_text(
            self.definition_version, "Experiment definition version"
        )
        dataset_identity = self._normalize_identity(
            self.dataset_identity, "Dataset identity"
        )
        universe_identity = self._normalize_identity(
            self.universe_identity, "Universe identity"
        )
        observation_as_of = self._normalize_timestamp(self.observation_as_of)
        factor_identities = self._normalize_identities(
            self.factor_identities, "Factor identities"
        )

        if self.signal_identity is not None:
            signal_identity = self._normalize_identity(
                self.signal_identity, "Signal identity"
            )
        else:
            signal_identity = None

        if self.strategy_identity is not None:
            strategy_identity = self._normalize_identity(
                self.strategy_identity, "Strategy identity"
            )
        else:
            strategy_identity = None

        parameters = self._normalize_parameters(self.parameters)
        code_version = self.code_version.strip() if isinstance(self.code_version, str) else None
        if code_version is None:
            raise InvalidInputError("Code version must be a string.")
        if not code_version:
            raise InvalidInputError("Code version must not be empty.")

        object.__setattr__(self, "experiment_key", experiment_key)
        object.__setattr__(self, "definition_version", definition_version)
        object.__setattr__(self, "dataset_identity", dataset_identity)
        object.__setattr__(self, "universe_identity", universe_identity)
        object.__setattr__(self, "observation_as_of", observation_as_of)
        object.__setattr__(self, "factor_identities", factor_identities)
        object.__setattr__(self, "signal_identity", signal_identity)
        object.__setattr__(self, "strategy_identity", strategy_identity)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "code_version", code_version)

    @property
    def identity(self) -> DefinitionIdentity:
        """Return the stable experiment-definition identity."""
        return self.experiment_key, self.definition_version

    @property
    def canonical_payload(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible snapshot of the run inputs."""
        return {
            "experiment": {
                "key": self.experiment_key,
                "definition_version": self.definition_version,
            },
            "dataset": self.dataset_identity,
            "universe": self.universe_identity,
            "observation_as_of": self.observation_as_of.isoformat(),
            "factors": self.factor_identities,
            "signal": self.signal_identity,
            "strategy": self.strategy_identity,
            "parameters": self.parameters,
            "code_version": self.code_version,
        }

    @property
    def run_input_fingerprint(self) -> str:
        """Return a deterministic SHA-256 fingerprint of the run inputs.

        The fingerprint excludes execution time and output artifacts so that the
        same experiment definition and research inputs resolve to the same input
        identity across repeated executions.
        """
        canonical = json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
            default=self._json_default,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _required_text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise InvalidInputError(f"{name} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _normalize_identity(
        identity: DefinitionIdentity,
        name: str,
    ) -> DefinitionIdentity:
        if not isinstance(identity, tuple) or len(identity) != 2:
            raise InvalidInputError(
                f"{name} must be a (key, definition_version) tuple."
            )
        key, version = identity
        if not isinstance(key, str) or not isinstance(version, str):
            raise InvalidInputError(
                f"{name} values must both be strings."
            )
        normalized = (key.strip(), version.strip())
        if not normalized[0] or not normalized[1]:
            raise InvalidInputError(f"{name} values must not be empty.")
        return normalized

    @classmethod
    def _normalize_identities(
        cls,
        identities: Iterable[DefinitionIdentity],
        name: str,
    ) -> tuple[DefinitionIdentity, ...]:
        normalized: list[DefinitionIdentity] = []
        seen: set[DefinitionIdentity] = set()
        for identity in tuple(identities):
            item = cls._normalize_identity(identity, name)
            if item in seen:
                raise InvalidInputError(f"{name} must not contain duplicates.")
            seen.add(item)
            normalized.append(item)
        return tuple(normalized)

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise InvalidInputError("Observation as-of must be a datetime.")
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidInputError(
                "Observation as-of must be timezone-aware."
            )
        normalized = value.astimezone(timezone.utc)
        if normalized > datetime.now(timezone.utc):
            raise InvalidInputError("Observation as-of must not be in the future.")
        return normalized

    @classmethod
    def _normalize_parameters(
        cls,
        parameters: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if parameters is None:
            return {}
        if not isinstance(parameters, Mapping):
            raise InvalidInputError("Experiment parameters must be a mapping.")
        try:
            normalized = cls._canonicalize(dict(parameters))
            json.dumps(
                normalized,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(
                "Experiment parameters must contain only deterministic JSON values."
            ) from exc
        return normalized

    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("Non-finite parameter.")
            return value
        if isinstance(value, Mapping):
            normalized = _FrozenDict()
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("Parameter mapping keys must be strings.")
                dict.__setitem__(normalized, key, cls._canonicalize(item))
            return _FrozenDict(
                (key, normalized[key]) for key in sorted(normalized)
            )
        if isinstance(value, (list, tuple)):
            return _FrozenList(cls._canonicalize(item) for item in value)
        raise TypeError(f"Unsupported parameter type: {type(value).__name__}")

    @staticmethod
    def _json_default(value: Any) -> Any:
        raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


class ResearchExperimentDefinitionRegistry:
    """Resolve versioned experiment definitions without persistence."""

    def __init__(
        self,
        definitions: Iterable[ResearchExperimentDefinition] = (),
    ):
        self._definitions: dict[
            DefinitionIdentity, ResearchExperimentDefinition
        ] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ResearchExperimentDefinition) -> None:
        if not isinstance(definition, ResearchExperimentDefinition):
            raise InvalidInputError(
                "Experiment registry accepts ResearchExperimentDefinition values."
            )
        if definition.identity in self._definitions:
            raise InvalidInputError(
                "Experiment definition identity is already registered."
            )
        self._definitions[definition.identity] = definition

    def definitions(self) -> tuple[ResearchExperimentDefinition, ...]:
        """Return definitions in deterministic registration order."""
        return tuple(self._definitions.values())

    def get(
        self,
        experiment_key: str,
        definition_version: str,
    ) -> ResearchExperimentDefinition:
        key = ResearchExperimentDefinition._required_text(
            experiment_key, "Experiment key"
        )
        version = ResearchExperimentDefinition._required_text(
            definition_version, "Experiment definition version"
        )
        definition = self._definitions.get((key, version))
        if definition is None:
            raise ResourceNotFoundError(
                f"Experiment definition not found: {key} v{version}"
            )
        return definition


@dataclass(frozen=True)
class ResearchExperimentRunView:
    """Stable read model for one persisted experiment run."""

    run_id: str
    experiment_key: str
    definition_version: str
    run_input_fingerprint: str
    definition_payload: dict
    status: ResearchExperimentRunStatus
    submitted_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_summary: str | None


class ResearchExperimentService:
    """Own the definition validation and persisted experiment-run boundary."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = ResearchExperimentRepository(db)

    @staticmethod
    def validate_definition(
        definition: ResearchExperimentDefinition,
    ) -> ResearchExperimentDefinition:
        if not isinstance(definition, ResearchExperimentDefinition):
            raise InvalidInputError(
                "Experiment validation requires a ResearchExperimentDefinition."
            )
        return definition

    @staticmethod
    def _validate_run_id(run_id: str) -> str:
        if not isinstance(run_id, str) or not run_id.strip():
            raise InvalidInputError("Experiment run id must be a non-empty string.")
        normalized = run_id.strip()
        if len(normalized) > 64:
            raise InvalidInputError("Experiment run id must be at most 64 characters.")
        return normalized

    @staticmethod
    def _view(run: ResearchExperimentRun) -> ResearchExperimentRunView:
        return ResearchExperimentRunView(
            run_id=run.run_id,
            experiment_key=run.experiment_key,
            definition_version=run.definition_version,
            run_input_fingerprint=run.run_input_fingerprint,
            definition_payload=run.definition_payload,
            status=run.status,
            submitted_at=run.submitted_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error_summary=run.error_summary,
        )

    def create_run(
        self,
        definition: ResearchExperimentDefinition,
        *,
        run_id: str | None = None,
    ) -> ResearchExperimentRunView:
        """Persist one queued run against an immutable definition snapshot."""
        definition = self.validate_definition(definition)
        normalized_run_id = (
            ResearchExperimentRun.new_run_id()
            if run_id is None
            else self._validate_run_id(run_id)
        )
        submitted_at = datetime.now(timezone.utc)
        try:
            run = self.repository.create(
                run_id=normalized_run_id,
                experiment_key=definition.experiment_key,
                definition_version=definition.definition_version,
                run_input_fingerprint=definition.run_input_fingerprint,
                definition_payload=definition.canonical_payload,
                submitted_at=submitted_at,
            )
            self.db.commit()
            return self._view(run)
        except IntegrityError as exc:
            self.db.rollback()
            raise InvalidInputError(
                f"Experiment run id '{normalized_run_id}' already exists."
            ) from exc

    def get_run(self, run_id: str) -> ResearchExperimentRunView:
        normalized_run_id = self._validate_run_id(run_id)
        run = self.repository.get(normalized_run_id)
        if run is None:
            raise ResourceNotFoundError(
                f"Experiment run not found: {normalized_run_id}"
            )
        return self._view(run)

    def start_run(self, run_id: str) -> dict[str, object]:
        return self._transition(
            run_id,
            expected_statuses=(ResearchExperimentRunStatus.QUEUED,),
            status=ResearchExperimentRunStatus.RUNNING,
        )

    def complete_run(self, run_id: str) -> dict[str, object]:
        return self._transition(
            run_id,
            expected_statuses=(ResearchExperimentRunStatus.RUNNING,),
            status=ResearchExperimentRunStatus.COMPLETED,
        )

    def fail_run(self, run_id: str, *, error_summary: str) -> dict[str, object]:
        if not isinstance(error_summary, str) or not error_summary.strip():
            raise InvalidInputError("Experiment run error summary must be a non-empty string.")
        return self._transition(
            run_id,
            expected_statuses=(ResearchExperimentRunStatus.RUNNING,),
            status=ResearchExperimentRunStatus.FAILED,
            error_summary=error_summary,
        )

    def cancel_run(self, run_id: str) -> dict[str, object]:
        return self._transition(
            run_id,
            expected_statuses=(
                ResearchExperimentRunStatus.QUEUED,
                ResearchExperimentRunStatus.RUNNING,
            ),
            status=ResearchExperimentRunStatus.CANCELLED,
        )

    def _transition(
        self,
        run_id: str,
        *,
        expected_statuses: tuple[ResearchExperimentRunStatus, ...],
        status: ResearchExperimentRunStatus,
        error_summary: str | None = None,
    ) -> ResearchExperimentRunView:
        normalized_run_id = self._validate_run_id(run_id)
        run = self.repository.get(normalized_run_id)
        if run is None:
            raise ResourceNotFoundError(
                f"Experiment run not found: {normalized_run_id}"
            )
        if run.status not in expected_statuses:
            allowed = ", ".join(item.value for item in expected_statuses)
            raise InvalidInputError(
                f"Experiment run {normalized_run_id} cannot transition from "
                f"{run.status.value}; expected one of: {allowed}."
            )

        now = datetime.now(timezone.utc)
        if not self.repository.transition(
            run,
            expected_statuses=expected_statuses,
            status=status,
            now=now,
            error_summary=error_summary,
        ):
            self.db.rollback()
            raise InvalidInputError(
                f"Experiment run {normalized_run_id} changed state concurrently."
            )
        self.db.commit()
        return self._view(run)
