from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Callable, Iterable, Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.models.research_experiment import (
    ResearchExperimentArtifact,
    ResearchExperimentComparisonResultRecord,
    ResearchExperimentRun,
    ResearchExperimentRunResult,
    ResearchExperimentRunStatus,
)
from quantcore.repositories.research_experiment_repository import ResearchExperimentRepository


def _validate_identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{name} must be a non-empty string.")
    normalized = value.strip()
    if len(normalized) > 64:
        raise InvalidInputError(f"{name} must be at most 64 characters.")
    return normalized


def _validate_sha256_fingerprint(value: str, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise InvalidInputError(f"{name} must be a SHA-256 hexadecimal string.")
    normalized = value.lower()
    if any(char not in "0123456789abcdef" for char in normalized):
        raise InvalidInputError(f"{name} must be a SHA-256 hexadecimal string.")
    return normalized


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

    @classmethod
    def from_canonical_payload(
        cls,
        payload: Mapping[str, Any],
    ) -> "ResearchExperimentDefinition":
        """Reconstruct and validate a persisted canonical definition snapshot."""
        if not isinstance(payload, Mapping):
            raise InvalidInputError(
                "Persisted experiment definition snapshot must be a mapping."
            )

        def identity(value: Any, name: str) -> DefinitionIdentity:
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise InvalidInputError(
                    f"Persisted {name} must be a two-item identity."
                )
            return value[0], value[1]

        try:
            experiment = payload["experiment"]
            dataset = payload["dataset"]
            universe = payload["universe"]
            observation_as_of = datetime.fromisoformat(payload["observation_as_of"])
            factors = tuple(
                identity(item, "factor identity")
                for item in payload["factors"]
            )
            signal = (
                None
                if payload["signal"] is None
                else identity(payload["signal"], "signal identity")
            )
            strategy = (
                None
                if payload["strategy"] is None
                else identity(payload["strategy"], "strategy identity")
            )
            parameters = payload["parameters"]
            code_version = payload["code_version"]
            experiment_key = experiment["key"]
            definition_version = experiment["definition_version"]
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidInputError(
                "Persisted experiment definition snapshot is invalid."
            ) from exc

        if not isinstance(experiment, Mapping):
            raise InvalidInputError(
                "Persisted experiment definition snapshot has an invalid experiment identity."
            )
        if not isinstance(payload.get("factors"), (list, tuple)):
            raise InvalidInputError(
                "Persisted experiment definition snapshot has invalid factor identities."
            )

        return cls(
            experiment_key=experiment_key,
            definition_version=definition_version,
            dataset_identity=identity(dataset, "dataset identity"),
            universe_identity=identity(universe, "universe identity"),
            observation_as_of=observation_as_of,
            factor_identities=factors,
            signal_identity=signal,
            strategy_identity=strategy,
            parameters=parameters,
            code_version=code_version,
        )

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
class ResearchExperimentExecutionResult:
    """Validated, JSON-compatible output contract for one experiment execution."""

    result_payload: Mapping[str, Any]
    metrics: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.result_payload, Mapping):
            raise InvalidInputError("Experiment result payload must be a mapping.")
        if self.metrics is not None and not isinstance(self.metrics, Mapping):
            raise InvalidInputError("Experiment result metrics must be a mapping.")
        try:
            payload = ResearchExperimentDefinition._canonicalize(
                dict(self.result_payload)
            )
            metrics = (
                ResearchExperimentDefinition._canonicalize(dict(self.metrics))
                if self.metrics is not None
                else {}
            )
            json.dumps(
                {"result": payload, "metrics": metrics},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(
                "Experiment results must contain only deterministic JSON values."
            ) from exc
        object.__setattr__(self, "result_payload", payload)
        object.__setattr__(self, "metrics", metrics)

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {"result": self.result_payload, "metrics": self.metrics}

    @property
    def result_fingerprint(self) -> str:
        canonical = json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchExperimentArtifactDefinition:
    """Immutable descriptor for one artifact produced by an experiment run.

    The provenance mapping is retained only as caller-supplied annotation for
    compatibility. It is deliberately excluded from artifact
    identity; authoritative lineage is derived from the persisted run/result
    state by ``get_artifact_provenance``.
    """

    run_id: str
    artifact_type: str
    content_hash: str
    metadata: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        run_id = _validate_identifier(self.run_id, "Experiment run id")
        artifact_type = self._required_text(self.artifact_type, "Artifact type")
        content_hash = self._normalize_hash(self.content_hash, "Content hash")
        metadata = self._normalize_mapping(self.metadata, "Artifact metadata")
        provenance = self._normalize_mapping(self.provenance, "Artifact provenance")

        canonical = {
            "run_id": run_id,
            "artifact_type": artifact_type,
            "content_hash": content_hash,
            "metadata": metadata,
        }
        try:
            json.dumps(
                canonical,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(
                "Artifact metadata and provenance must contain only deterministic JSON values."
            ) from exc

        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "artifact_type", artifact_type)
        object.__setattr__(self, "content_hash", content_hash)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "provenance", provenance)

    @staticmethod
    def _required_text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise InvalidInputError(f"{name} must be a non-empty string.")
        normalized = value.strip()
        if len(normalized) > 100:
            raise InvalidInputError(f"{name} must be at most 100 characters.")
        return normalized

    @staticmethod
    def _normalize_hash(value: str, name: str) -> str:
        if not isinstance(value, str):
            raise InvalidInputError(f"{name} must be a SHA-256 hexadecimal string.")
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise InvalidInputError(f"{name} must be a SHA-256 hexadecimal string.")
        return normalized

    @classmethod
    def _normalize_mapping(
        cls, value: Mapping[str, Any] | None, name: str
    ) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise InvalidInputError(f"{name} must be a mapping.")
        try:
            return ResearchExperimentDefinition._canonicalize(dict(value))
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(
                f"{name} must contain only deterministic JSON values."
            ) from exc

    @property
    def canonical_payload(self) -> dict[str, Any]:
        """Return the identity payload for the artifact descriptor.

        Caller-supplied provenance is intentionally absent. It must not be able
        to change artifact identity or create competing identities for the same
        artifact descriptor.
        """
        return {
            "run_id": self.run_id,
            "artifact_type": self.artifact_type,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }

    @property
    def artifact_fingerprint(self) -> str:
        canonical = json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchExperimentArtifactProvenance:
    """Authoritative read contract linking an artifact to its persisted run inputs."""

    artifact_id: str
    artifact_type: str
    content_hash: str
    artifact_fingerprint: str
    run_id: str
    definition: ResearchExperimentDefinition
    result_fingerprint: str | None = None

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "artifact": {
                "id": self.artifact_id,
                "type": self.artifact_type,
                "content_hash": self.content_hash,
                "fingerprint": self.artifact_fingerprint,
            },
            "run": {
                "run_id": self.run_id,
                "definition": self.definition.canonical_payload,
                "run_input_fingerprint": self.definition.run_input_fingerprint,
            },
            "result": {
                "result_fingerprint": self.result_fingerprint,
            },
        }

    @property
    def provenance_fingerprint(self) -> str:
        canonical = json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchExperimentArtifactView:
    """Stable read model for one persisted experiment artifact descriptor."""

    artifact_id: str
    run_id: str
    artifact_type: str
    content_hash: str
    artifact_fingerprint: str
    metadata: dict
    provenance: dict
    created_at: datetime


@dataclass(frozen=True)
class ResearchExperimentRunQuery:
    """Validated bounded query contract for experiment run discovery."""

    experiment_key: str | None = None
    definition_version: str | None = None
    statuses: tuple[ResearchExperimentRunStatus, ...] = ()
    submitted_after: datetime | None = None
    submitted_before: datetime | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        experiment_key = self._normalize_optional_text(
            self.experiment_key, "Experiment key", max_length=200
        )
        definition_version = self._normalize_optional_text(
            self.definition_version, "Experiment definition version", max_length=50
        )
        statuses = tuple(self.statuses)
        if any(
            not isinstance(status, ResearchExperimentRunStatus)
            for status in statuses
        ):
            raise InvalidInputError(
                "Experiment run statuses must contain "
                "ResearchExperimentRunStatus values."
            )
        if len(statuses) != len(set(statuses)):
            raise InvalidInputError(
                "Experiment run statuses must not contain duplicates."
            )
        submitted_after = self._normalize_optional_timestamp(
            self.submitted_after, "Submitted-after"
        )
        submitted_before = self._normalize_optional_timestamp(
            self.submitted_before, "Submitted-before"
        )
        if (
            submitted_after is not None
            and submitted_before is not None
            and submitted_after > submitted_before
        ):
            raise InvalidInputError(
                "Submitted-after must not be later than submitted-before."
            )
        if not isinstance(self.limit, int) or isinstance(self.limit, bool):
            raise InvalidInputError("Experiment run query limit must be an integer.")
        if self.limit < 1 or self.limit > 100:
            raise InvalidInputError(
                "Experiment run query limit must be between 1 and 100."
            )

        object.__setattr__(self, "experiment_key", experiment_key)
        object.__setattr__(self, "definition_version", definition_version)
        object.__setattr__(self, "statuses", statuses)
        object.__setattr__(self, "submitted_after", submitted_after)
        object.__setattr__(self, "submitted_before", submitted_before)

    @staticmethod
    def _normalize_optional_text(
        value: str | None, name: str, *, max_length: int
    ) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise InvalidInputError(
                f"{name} must be a non-empty string when provided."
            )
        normalized = value.strip()
        if len(normalized) > max_length:
            raise InvalidInputError(
                f"{name} must be at most {max_length} characters."
            )
        return normalized

    @staticmethod
    def _normalize_optional_timestamp(
        value: datetime | None, name: str
    ) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise InvalidInputError(f"{name} must be a datetime when provided.")
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidInputError(f"{name} must be timezone-aware.")
        return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ResearchExperimentRunSelection:
    """Immutable bounded set of persisted run identities for higher-level research."""

    run_ids: tuple[str, ...]
    experiment_key: str | None = None
    definition_version: str | None = None
    max_runs: int = 100

    def __post_init__(self) -> None:
        normalized_ids = tuple(
            _validate_identifier(run_id, "Experiment run id")
            for run_id in tuple(self.run_ids)
        )
        if not normalized_ids:
            raise InvalidInputError("Experiment run selection must contain at least one run id.")
        if len(normalized_ids) != len(set(normalized_ids)):
            raise InvalidInputError("Experiment run selection must not contain duplicates.")

        experiment_key = self._normalize_optional_text(
            self.experiment_key, "Experiment key", max_length=200
        )
        definition_version = self._normalize_optional_text(
            self.definition_version, "Experiment definition version", max_length=50
        )
        if not isinstance(self.max_runs, int) or isinstance(self.max_runs, bool):
            raise InvalidInputError("Experiment run selection max_runs must be an integer.")
        if self.max_runs < 1 or self.max_runs > 100:
            raise InvalidInputError(
                "Experiment run selection max_runs must be between 1 and 100."
            )
        if len(normalized_ids) > self.max_runs:
            raise InvalidInputError(
                "Experiment run selection cannot contain more than max_runs run ids."
            )

        object.__setattr__(self, "run_ids", tuple(sorted(normalized_ids)))
        object.__setattr__(self, "experiment_key", experiment_key)
        object.__setattr__(self, "definition_version", definition_version)

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "run_ids": self.run_ids,
            "experiment": {
                "key": self.experiment_key,
                "definition_version": self.definition_version,
            },
        }

    @property
    def selection_fingerprint(self) -> str:
        canonical = json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_optional_text(
        value: str | None, name: str, *, max_length: int
    ) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise InvalidInputError(
                f"{name} must be a non-empty string when provided."
            )
        normalized = value.strip()
        if len(normalized) > max_length:
            raise InvalidInputError(
                f"{name} must be at most {max_length} characters."
            )
        return normalized


@dataclass(frozen=True)
class ResearchExperimentComparisonRun:
    """Immutable identity snapshot for one run participating in a comparison."""

    run_id: str
    experiment_key: str
    definition_version: str
    run_input_fingerprint: str
    result_fingerprint: str

    def __post_init__(self) -> None:
        run_id = _validate_identifier(self.run_id, "Experiment run id")
        experiment_key = ResearchExperimentRunQuery._normalize_optional_text(
            self.experiment_key, "Experiment key", max_length=200
        )
        definition_version = ResearchExperimentRunQuery._normalize_optional_text(
            self.definition_version, "Experiment definition version", max_length=50
        )
        if experiment_key is None or definition_version is None:
            raise InvalidInputError(
                "Comparison run experiment identity must be complete."
            )
        run_input_fingerprint = _validate_sha256_fingerprint(
            self.run_input_fingerprint, "Run input fingerprint"
        )
        result_fingerprint = _validate_sha256_fingerprint(
            self.result_fingerprint, "Result fingerprint"
        )
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "experiment_key", experiment_key)
        object.__setattr__(self, "definition_version", definition_version)
        object.__setattr__(self, "run_input_fingerprint", run_input_fingerprint)
        object.__setattr__(self, "result_fingerprint", result_fingerprint)

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment": {
                "key": self.experiment_key,
                "definition_version": self.definition_version,
            },
            "run_input_fingerprint": self.run_input_fingerprint,
            "result_fingerprint": self.result_fingerprint,
        }


@dataclass(frozen=True)
class ResearchExperimentComparison:
    """Immutable identity contract for a multi-run experiment comparison."""

    selection_fingerprint: str
    experiment_key: str
    definition_version: str
    runs: tuple[ResearchExperimentComparisonRun, ...]

    def __post_init__(self) -> None:
        selection_fingerprint = _validate_sha256_fingerprint(
            self.selection_fingerprint, "Comparison selection fingerprint"
        )
        experiment_key = ResearchExperimentRunQuery._normalize_optional_text(
            self.experiment_key, "Experiment key", max_length=200
        )
        definition_version = ResearchExperimentRunQuery._normalize_optional_text(
            self.definition_version, "Experiment definition version", max_length=50
        )
        if experiment_key is None or definition_version is None:
            raise InvalidInputError("Comparison experiment identity must be complete.")
        runs = tuple(self.runs)
        if len(runs) < 2:
            raise InvalidInputError("Experiment comparison must contain at least two runs.")
        if any(not isinstance(run, ResearchExperimentComparisonRun) for run in runs):
            raise InvalidInputError(
                "Experiment comparison runs must contain ResearchExperimentComparisonRun values."
            )
        run_ids = tuple(run.run_id for run in runs)
        if len(run_ids) != len(set(run_ids)):
            raise InvalidInputError("Experiment comparison runs must not contain duplicates.")
        if any(
            run.experiment_key != experiment_key
            or run.definition_version != definition_version
            for run in runs
        ):
            raise InvalidInputError(
                "Experiment comparison runs must share the comparison experiment identity."
            )
        object.__setattr__(self, "selection_fingerprint", selection_fingerprint)
        object.__setattr__(self, "experiment_key", experiment_key)
        object.__setattr__(self, "definition_version", definition_version)
        object.__setattr__(self, "runs", tuple(sorted(runs, key=lambda run: run.run_id)))

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "selection_fingerprint": self.selection_fingerprint,
            "experiment": {
                "key": self.experiment_key,
                "definition_version": self.definition_version,
            },
            "runs": tuple(run.canonical_payload for run in self.runs),
        }

    @property
    def comparison_fingerprint(self) -> str:
        canonical = json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()



@dataclass(frozen=True)
class ResearchExperimentComparisonMetric:
    """Immutable aligned numeric metric values for comparison participants."""

    metric_name: str
    values: tuple[tuple[str, int | float], ...]

    def __post_init__(self) -> None:
        metric_name = ResearchExperimentRunQuery._normalize_optional_text(
            self.metric_name, "Comparison metric name", max_length=100
        )
        if metric_name is None:
            raise InvalidInputError("Comparison metric name must be provided.")

        values = tuple(self.values)
        if len(values) < 2:
            raise InvalidInputError(
                "Comparison metric must contain at least two run values."
            )

        normalized_values: list[tuple[str, int | float]] = []
        run_ids: set[str] = set()
        for value in values:
            if not isinstance(value, (tuple, list)) or len(value) != 2:
                raise InvalidInputError(
                    "Comparison metric values must contain run id and numeric value pairs."
                )
            run_id = _validate_identifier(value[0], "Comparison metric run id")
            metric_value = value[1]
            if isinstance(metric_value, bool) or not isinstance(
                metric_value, (int, float)
            ):
                raise InvalidInputError(
                    "Comparison metric values must be finite numeric values."
                )
            if not math.isfinite(float(metric_value)):
                raise InvalidInputError(
                    "Comparison metric values must be finite numeric values."
                )
            if run_id in run_ids:
                raise InvalidInputError(
                    "Comparison metric values must not contain duplicate run ids."
                )
            run_ids.add(run_id)
            normalized_values.append((run_id, metric_value))

        object.__setattr__(self, "metric_name", metric_name)
        object.__setattr__(
            self,
            "values",
            tuple(sorted(normalized_values, key=lambda item: item[0])),
        )

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "values": tuple(
                {"run_id": run_id, "value": value}
                for run_id, value in self.values
            ),
        }


@dataclass(frozen=True)
class ResearchExperimentComparisonResult:
    """Immutable deterministic result containing aligned comparison metrics."""

    comparison_fingerprint: str
    metrics: tuple[ResearchExperimentComparisonMetric, ...]

    def __post_init__(self) -> None:
        comparison_fingerprint = _validate_sha256_fingerprint(
            self.comparison_fingerprint, "Comparison fingerprint"
        )
        metrics = tuple(self.metrics)
        if not metrics:
            raise InvalidInputError("Comparison result must contain at least one metric.")
        if any(
            not isinstance(metric, ResearchExperimentComparisonMetric)
            for metric in metrics
        ):
            raise InvalidInputError(
                "Comparison result metrics must contain ResearchExperimentComparisonMetric values."
            )
        metric_names = tuple(metric.metric_name for metric in metrics)
        if len(metric_names) != len(set(metric_names)):
            raise InvalidInputError(
                "Comparison result metrics must not contain duplicate names."
            )

        participant_run_ids = tuple(run_id for run_id, _ in metrics[0].values)
        participant_run_id_set = set(participant_run_ids)
        if any(
            {run_id for run_id, _ in metric.values} != participant_run_id_set
            for metric in metrics[1:]
        ):
            raise InvalidInputError(
                "Comparison result metrics must contain the same run ids."
            )

        object.__setattr__(self, "comparison_fingerprint", comparison_fingerprint)
        object.__setattr__(
            self,
            "metrics",
            tuple(sorted(metrics, key=lambda metric: metric.metric_name)),
        )

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "comparison_fingerprint": self.comparison_fingerprint,
            "metrics": tuple(metric.canonical_payload for metric in self.metrics),
        }

    @property
    def result_fingerprint(self) -> str:
        canonical = json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchExperimentComparisonResultView:
    """Stable read model for one persisted comparison-result snapshot."""

    comparison_fingerprint: str
    selection_fingerprint: str
    experiment_key: str
    definition_version: str
    comparison_payload: dict
    result_payload: dict
    result_fingerprint: str
    recorded_at: datetime


@dataclass(frozen=True)
class ResearchExperimentRunResultView:
    """Stable read model for one persisted experiment result."""

    run_id: str
    result_payload: dict
    metrics: dict
    result_fingerprint: str
    recorded_at: datetime


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
    def validate_comparison_result(
        comparison: ResearchExperimentComparison,
        result: ResearchExperimentComparisonResult,
    ) -> ResearchExperimentComparisonResult:
        """Validate that a comparison result belongs to the supplied comparison."""
        if not isinstance(comparison, ResearchExperimentComparison):
            raise InvalidInputError(
                "Comparison result validation requires a ResearchExperimentComparison."
            )
        if not isinstance(result, ResearchExperimentComparisonResult):
            raise InvalidInputError(
                "Comparison result validation requires a ResearchExperimentComparisonResult."
            )
        if result.comparison_fingerprint != comparison.comparison_fingerprint:
            raise InvalidInputError(
                "Comparison result does not match the supplied comparison identity."
            )

        expected_run_ids = {run.run_id for run in comparison.runs}
        result_run_ids = {run_id for run_id, _ in result.metrics[0].values}
        if result_run_ids != expected_run_ids:
            raise InvalidInputError(
                "Comparison result participants do not match the supplied comparison."
            )
        return result

    @staticmethod
    def _comparison_result_view(
        record: ResearchExperimentComparisonResultRecord,
    ) -> ResearchExperimentComparisonResultView:
        comparison_payload = record.comparison_payload
        result_payload = record.result_payload
        if not isinstance(comparison_payload, Mapping) or not isinstance(
            result_payload, Mapping
        ):
            raise InvalidInputError(
                "Persisted comparison result snapshots must contain mapping payloads."
            )

        if ResearchExperimentService._payload_fingerprint(comparison_payload) != (
            record.comparison_fingerprint
        ):
            raise InvalidInputError(
                "Persisted comparison result has an inconsistent comparison fingerprint."
            )
        if ResearchExperimentService._payload_fingerprint(result_payload) != (
            record.result_fingerprint
        ):
            raise InvalidInputError(
                "Persisted comparison result has an inconsistent result fingerprint."
            )

        experiment = comparison_payload.get("experiment")
        if not isinstance(experiment, Mapping):
            raise InvalidInputError(
                "Persisted comparison result has an invalid experiment identity."
            )
        if comparison_payload.get("selection_fingerprint") != record.selection_fingerprint:
            raise InvalidInputError(
                "Persisted comparison result has an inconsistent selection fingerprint."
            )
        if experiment.get("key") != record.experiment_key or experiment.get(
            "definition_version"
        ) != record.definition_version:
            raise InvalidInputError(
                "Persisted comparison result has an inconsistent experiment identity."
            )
        if result_payload.get("comparison_fingerprint") != record.comparison_fingerprint:
            raise InvalidInputError(
                "Persisted comparison result is linked to a different comparison."
            )

        return ResearchExperimentComparisonResultView(
            comparison_fingerprint=record.comparison_fingerprint,
            selection_fingerprint=record.selection_fingerprint,
            experiment_key=record.experiment_key,
            definition_version=record.definition_version,
            comparison_payload=dict(comparison_payload),
            result_payload=dict(result_payload),
            result_fingerprint=record.result_fingerprint,
            recorded_at=record.recorded_at,
        )

    @staticmethod
    def _payload_fingerprint(payload: Mapping[str, Any]) -> str:
        return sha256(
            ResearchExperimentService._canonical_json(payload).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _canonical_json(payload: Mapping[str, Any]) -> str:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    @staticmethod
    def _validate_run_id(run_id: str) -> str:
        return _validate_identifier(run_id, "Experiment run id")

    @staticmethod
    def _validate_artifact_id(artifact_id: str) -> str:
        return _validate_identifier(artifact_id, "Experiment artifact id")

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

    def list_runs(
        self,
        query: ResearchExperimentRunQuery | None = None,
    ) -> tuple[ResearchExperimentRunView, ...]:
        """Return a bounded, deterministically ordered set of matching runs."""
        if query is None:
            query = ResearchExperimentRunQuery()
        if not isinstance(query, ResearchExperimentRunQuery):
            raise InvalidInputError(
                "Experiment run discovery requires a ResearchExperimentRunQuery."
            )
        return tuple(
            self._view(run)
            for run in self.repository.list_runs(
                experiment_key=query.experiment_key,
                definition_version=query.definition_version,
                statuses=query.statuses,
                submitted_after=query.submitted_after,
                submitted_before=query.submitted_before,
                limit=query.limit,
            )
        )

    def select_runs(
        self, selection: ResearchExperimentRunSelection
    ) -> tuple[ResearchExperimentRunView, ...]:
        """Resolve a validated run selection against persisted experiment runs."""
        if not isinstance(selection, ResearchExperimentRunSelection):
            raise InvalidInputError(
                "Experiment run selection requires a ResearchExperimentRunSelection."
            )

        runs = self.repository.get_by_run_ids(selection.run_ids)
        found_ids = {run.run_id for run in runs}
        missing_ids = [run_id for run_id in selection.run_ids if run_id not in found_ids]
        if missing_ids:
            raise ResourceNotFoundError(
                "Experiment runs not found: " + ", ".join(missing_ids)
            )

        if selection.experiment_key is not None:
            mismatched = [
                run.run_id
                for run in runs
                if run.experiment_key != selection.experiment_key
            ]
            if mismatched:
                raise InvalidInputError(
                    "Experiment run selection contains runs outside the requested "
                    f"experiment key: {', '.join(mismatched)}."
                )

        if selection.definition_version is not None:
            mismatched = [
                run.run_id
                for run in runs
                if run.definition_version != selection.definition_version
            ]
            if mismatched:
                raise InvalidInputError(
                    "Experiment run selection contains runs outside the requested "
                    f"definition version: {', '.join(mismatched)}."
                )

        return tuple(self._view(run) for run in runs)

    def compare_runs(
        self, selection: ResearchExperimentRunSelection
    ) -> ResearchExperimentComparison:
        """Resolve a run selection into a deterministic comparison identity contract."""
        if not isinstance(selection, ResearchExperimentRunSelection):
            raise InvalidInputError(
                "Experiment comparison requires a ResearchExperimentRunSelection."
            )
        runs = self.select_runs(selection)
        if len(runs) < 2:
            raise InvalidInputError(
                "Experiment comparison must contain at least two runs."
            )

        experiment_identity = {(run.experiment_key, run.definition_version) for run in runs}
        if len(experiment_identity) != 1:
            raise InvalidInputError(
                "Experiment comparison runs must share the same experiment identity."
            )
        experiment_key, definition_version = next(iter(experiment_identity))

        persisted_results = self.repository.get_results_by_run_ids(selection.run_ids)
        results_by_run_id = {result.run_id: result for result in persisted_results}
        missing_ids = [
            run_id for run_id in selection.run_ids if run_id not in results_by_run_id
        ]
        if missing_ids:
            raise ResourceNotFoundError(
                "Experiment results not found for runs: " + ", ".join(missing_ids)
            )

        comparison_runs = tuple(
            ResearchExperimentComparisonRun(
                run_id=run.run_id,
                experiment_key=run.experiment_key,
                definition_version=run.definition_version,
                run_input_fingerprint=run.run_input_fingerprint,
                result_fingerprint=results_by_run_id[run.run_id].result_fingerprint,
            )
            for run in runs
        )
        return ResearchExperimentComparison(
            selection_fingerprint=selection.selection_fingerprint,
            experiment_key=experiment_key,
            definition_version=definition_version,
            runs=comparison_runs,
        )

    def build_comparison_result(
        self,
        selection: ResearchExperimentRunSelection,
        metric_names: Iterable[str],
    ) -> ResearchExperimentComparisonResult:
        """Build a deterministic aligned numeric metric result for selected runs."""
        comparison = self.compare_runs(selection)

        if isinstance(metric_names, (str, bytes)):
            raise InvalidInputError("Comparison metric names must be an iterable of names.")

        normalized_metric_names: list[str] = []
        seen_names: set[str] = set()
        try:
            raw_metric_names = tuple(metric_names)
        except TypeError as exc:
            raise InvalidInputError(
                "Comparison metric names must be an iterable of names."
            ) from exc

        if not raw_metric_names:
            raise InvalidInputError("Comparison requires at least one metric name.")
        if len(raw_metric_names) > 50:
            raise InvalidInputError("Comparison supports at most 50 metric names.")

        for name in raw_metric_names:
            normalized = ResearchExperimentRunQuery._normalize_optional_text(
                name, "Comparison metric name", max_length=100
            )
            if normalized is None:
                raise InvalidInputError("Comparison metric name must be provided.")
            if normalized in seen_names:
                raise InvalidInputError(
                    "Comparison metric names must not contain duplicates."
                )
            seen_names.add(normalized)
            normalized_metric_names.append(normalized)

        persisted_results = self.repository.get_results_by_run_ids(selection.run_ids)
        results_by_run_id = {result.run_id: result for result in persisted_results}

        metrics: list[ResearchExperimentComparisonMetric] = []
        for metric_name in normalized_metric_names:
            values: list[tuple[str, int | float]] = []
            missing_runs: list[str] = []
            for run in comparison.runs:
                result = results_by_run_id[run.run_id]
                if metric_name not in result.metrics:
                    missing_runs.append(run.run_id)
                    continue
                values.append((run.run_id, result.metrics[metric_name]))

            if missing_runs:
                raise InvalidInputError(
                    f"Comparison metric '{metric_name}' is missing for runs: "
                    + ", ".join(missing_runs)
                    + "."
                )

            metrics.append(
                ResearchExperimentComparisonMetric(
                    metric_name=metric_name,
                    values=tuple(values),
                )
            )

        result = ResearchExperimentComparisonResult(
            comparison_fingerprint=comparison.comparison_fingerprint,
            metrics=tuple(metrics),
        )
        return self.validate_comparison_result(comparison, result)

    def record_comparison_result(
        self,
        comparison: ResearchExperimentComparison,
        result: ResearchExperimentComparisonResult,
    ) -> ResearchExperimentComparisonResultView:
        """Persist one immutable comparison-result snapshot idempotently."""
        self.validate_comparison_result(comparison, result)

        result_fingerprint = result.result_fingerprint
        existing = self.repository.get_comparison_result(result_fingerprint)
        if existing is not None:
            return self._comparison_result_view(existing)

        recorded_at = datetime.now(timezone.utc)
        try:
            persisted = self.repository.create_comparison_result(
                comparison_fingerprint=comparison.comparison_fingerprint,
                selection_fingerprint=comparison.selection_fingerprint,
                experiment_key=comparison.experiment_key,
                definition_version=comparison.definition_version,
                comparison_payload=comparison.canonical_payload,
                result_payload=result.canonical_payload,
                result_fingerprint=result_fingerprint,
                recorded_at=recorded_at,
            )
            self.db.commit()
            return self._comparison_result_view(persisted)
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.repository.get_comparison_result(result_fingerprint)
            if existing is not None:
                return self._comparison_result_view(existing)
            raise InvalidInputError(
                "Comparison result could not be persisted."
            ) from exc

    def get_comparison_result(
        self, result_fingerprint: str
    ) -> ResearchExperimentComparisonResultView:
        normalized_fingerprint = _validate_sha256_fingerprint(
            result_fingerprint, "Comparison result fingerprint"
        )
        record = self.repository.get_comparison_result(normalized_fingerprint)
        if record is None:
            raise ResourceNotFoundError(
                f"Comparison result not found: {normalized_fingerprint}"
            )
        return self._comparison_result_view(record)

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

    @staticmethod
    def validate_artifact(
        artifact: ResearchExperimentArtifactDefinition,
    ) -> ResearchExperimentArtifactDefinition:
        if not isinstance(artifact, ResearchExperimentArtifactDefinition):
            raise InvalidInputError(
                "Artifact validation requires a ResearchExperimentArtifactDefinition."
            )
        return artifact

    @staticmethod
    def _artifact_view(
        artifact: ResearchExperimentArtifact,
    ) -> ResearchExperimentArtifactView:
        return ResearchExperimentArtifactView(
            artifact_id=artifact.artifact_id,
            run_id=artifact.run_id,
            artifact_type=artifact.artifact_type,
            content_hash=artifact.content_hash,
            artifact_fingerprint=artifact.artifact_fingerprint,
            metadata=artifact.artifact_metadata,
            provenance=artifact.provenance,
            created_at=artifact.created_at,
        )

    def create_artifact(
        self,
        artifact: ResearchExperimentArtifactDefinition,
        *,
        artifact_id: str | None = None,
    ) -> ResearchExperimentArtifactView:
        """Persist one immutable artifact descriptor against an existing run."""
        artifact = self.validate_artifact(artifact)
        normalized_artifact_id = (
            ResearchExperimentArtifact.new_artifact_id()
            if artifact_id is None
            else self._validate_artifact_id(artifact_id)
        )
        run_id = self._validate_run_id(artifact.run_id)
        if self.repository.get(run_id) is None:
            raise ResourceNotFoundError(f"Experiment run not found: {run_id}")
        if self.repository.get_artifact(normalized_artifact_id) is not None:
            raise InvalidInputError(
                f"Experiment artifact id '{normalized_artifact_id}' already exists."
            )
        if self.repository.get_artifact_by_fingerprint(
            run_id, artifact.artifact_fingerprint
        ) is not None:
            raise InvalidInputError(
                "An artifact with the same identity is already registered for this run."
            )

        created_at = datetime.now(timezone.utc)
        try:
            persisted = self.repository.create_artifact(
                artifact_id=normalized_artifact_id,
                run_id=run_id,
                artifact_type=artifact.artifact_type,
                content_hash=artifact.content_hash,
                artifact_fingerprint=artifact.artifact_fingerprint,
                metadata=dict(artifact.metadata),
                provenance=dict(artifact.provenance),
                created_at=created_at,
            )
            self.db.commit()
            return self._artifact_view(persisted)
        except IntegrityError as exc:
            self.db.rollback()
            if self.repository.get_artifact_by_fingerprint(
                run_id, artifact.artifact_fingerprint
            ) is not None:
                raise InvalidInputError(
                    "An artifact with the same identity is already registered for this run."
                ) from exc
            raise InvalidInputError(
                f"Experiment artifact id '{normalized_artifact_id}' already exists."
            ) from exc

    def list_artifacts(self, run_id: str) -> tuple[ResearchExperimentArtifactView, ...]:
        normalized_run_id = self._validate_run_id(run_id)
        if self.repository.get(normalized_run_id) is None:
            raise ResourceNotFoundError(
                f"Experiment run not found: {normalized_run_id}"
            )
        return tuple(
            self._artifact_view(artifact)
            for artifact in self.repository.list_artifacts(normalized_run_id)
        )

    def get_artifact(self, artifact_id: str) -> ResearchExperimentArtifactView:
        normalized_artifact_id = self._validate_artifact_id(artifact_id)
        artifact = self.repository.get_artifact(normalized_artifact_id)
        if artifact is None:
            raise ResourceNotFoundError(
                f"Experiment artifact not found: {normalized_artifact_id}"
            )
        return self._artifact_view(artifact)

    def get_artifact_provenance(
        self,
        artifact_id: str,
    ) -> ResearchExperimentArtifactProvenance:
        """Return authoritative provenance derived from persisted run and result state.

        The artifact's caller-supplied provenance field is deliberately excluded
        from this contract. The persisted run definition snapshot and result
        fingerprint are the source of truth for the experiment lineage.
        """
        normalized_artifact_id = self._validate_artifact_id(artifact_id)
        artifact = self.repository.get_artifact(normalized_artifact_id)
        if artifact is None:
            raise ResourceNotFoundError(
                f"Experiment artifact not found: {normalized_artifact_id}"
            )

        run = self.repository.get(artifact.run_id)
        if run is None:
            raise InvalidInputError(
                f"Experiment artifact {normalized_artifact_id} references a missing run."
            )

        definition = ResearchExperimentDefinition.from_canonical_payload(
            run.definition_payload
        )
        if (
            definition.experiment_key != run.experiment_key
            or definition.definition_version != run.definition_version
            or definition.run_input_fingerprint != run.run_input_fingerprint
        ):
            raise InvalidInputError(
                f"Persisted experiment run {run.run_id} has an inconsistent definition snapshot."
            )

        result = self.repository.get_result(run.run_id)
        return ResearchExperimentArtifactProvenance(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            content_hash=artifact.content_hash,
            artifact_fingerprint=artifact.artifact_fingerprint,
            run_id=run.run_id,
            definition=definition,
            result_fingerprint=(
                result.result_fingerprint if result is not None else None
            ),
        )

    def get_result(self, run_id: str) -> ResearchExperimentRunResultView:
        normalized_run_id = self._validate_run_id(run_id)
        result = self.repository.get_result(normalized_run_id)
        if result is None:
            raise ResourceNotFoundError(
                f"Experiment result not found for run: {normalized_run_id}"
            )
        return ResearchExperimentRunResultView(
            run_id=result.run_id,
            result_payload=result.result_payload,
            metrics=result.metrics,
            result_fingerprint=result.result_fingerprint,
            recorded_at=result.recorded_at,
        )

    def execute_run(
        self,
        run_id: str,
        definition: ResearchExperimentDefinition,
        executor: Callable[
            [ResearchExperimentDefinition], ResearchExperimentExecutionResult
        ],
    ) -> ResearchExperimentRunResultView:
        """Execute one queued run and persist exactly one validated result.

        The executor is deliberately supplied by the caller: this boundary owns
        lifecycle/result persistence, not experiment-specific orchestration.
        """
        if not callable(executor):
            raise InvalidInputError("Experiment executor must be callable.")
        definition = self.validate_definition(definition)
        normalized_run_id = self._validate_run_id(run_id)
        run = self.repository.get(normalized_run_id)
        if run is None:
            raise ResourceNotFoundError(
                f"Experiment run not found: {normalized_run_id}"
            )
        if run.status is not ResearchExperimentRunStatus.QUEUED:
            raise InvalidInputError(
                f"Experiment run {normalized_run_id} is not queued."
            )
        if (
            run.experiment_key != definition.experiment_key
            or run.definition_version != definition.definition_version
            or run.run_input_fingerprint != definition.run_input_fingerprint
        ):
            raise InvalidInputError(
                "Experiment definition does not match the persisted run inputs."
            )

        self.start_run(normalized_run_id)

        try:
            execution_result = executor(definition)
            if not isinstance(execution_result, ResearchExperimentExecutionResult):
                raise InvalidInputError(
                    "Experiment executor must return ResearchExperimentExecutionResult."
                )
            existing = self.repository.get_result(normalized_run_id)
            if existing is not None:
                raise InvalidInputError(
                    f"Experiment result already exists for run: {normalized_run_id}"
                )
            recorded_at = datetime.now(timezone.utc)
            result = self.repository.create_result(
                run_id=normalized_run_id,
                result_payload=execution_result.result_payload,
                metrics=execution_result.metrics,
                result_fingerprint=execution_result.result_fingerprint,
                recorded_at=recorded_at,
            )
            current = self.repository.get(normalized_run_id)
            if current is None or current.status is not ResearchExperimentRunStatus.RUNNING:
                self.db.rollback()
                raise InvalidInputError(
                    f"Experiment run {normalized_run_id} changed state concurrently."
                )
            completed = self.repository.transition(
                current,
                expected_statuses=(ResearchExperimentRunStatus.RUNNING,),
                status=ResearchExperimentRunStatus.COMPLETED,
                now=recorded_at,
            )
            if not completed:
                self.db.rollback()
                raise InvalidInputError(
                    f"Experiment run {normalized_run_id} changed state concurrently."
                )
            self.db.commit()
            return ResearchExperimentRunResultView(
                run_id=result.run_id,
                result_payload=result.result_payload,
                metrics=result.metrics,
                result_fingerprint=result.result_fingerprint,
                recorded_at=result.recorded_at,
            )
        except Exception as exc:
            self.db.rollback()
            current = self.repository.get(normalized_run_id)
            if (
                current is not None
                and current.status is ResearchExperimentRunStatus.RUNNING
            ):
                if self.repository.transition(
                    current,
                    expected_statuses=(ResearchExperimentRunStatus.RUNNING,),
                    status=ResearchExperimentRunStatus.FAILED,
                    now=datetime.now(timezone.utc),
                    error_summary=str(exc),
                ):
                    self.db.commit()
                else:
                    self.db.rollback()
            raise

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
