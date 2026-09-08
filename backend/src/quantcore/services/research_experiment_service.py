from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError


DefinitionIdentity = tuple[str, str]
ResearchSignalIdentity = DefinitionIdentity
ResearchStrategyIdentity = DefinitionIdentity


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
    def run_input_fingerprint(self) -> str:
        """Return a deterministic SHA-256 fingerprint of the run inputs.

        The fingerprint excludes execution time and output artifacts so that the
        same experiment definition and research inputs resolve to the same input
        identity across repeated executions.
        """
        payload = {
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
        canonical = json.dumps(
            payload,
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
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("Parameter mapping keys must be strings.")
                normalized[key] = cls._canonicalize(item)
            return {key: normalized[key] for key in sorted(normalized)}
        if isinstance(value, (list, tuple)):
            return [cls._canonicalize(item) for item in value]
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


class ResearchExperimentService:
    """Validate the versioned experiment-definition boundary."""

    @staticmethod
    def validate_definition(
        definition: ResearchExperimentDefinition,
    ) -> ResearchExperimentDefinition:
        if not isinstance(definition, ResearchExperimentDefinition):
            raise InvalidInputError(
                "Experiment validation requires a ResearchExperimentDefinition."
            )
        return definition
