from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Iterable

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError


ResearchSignalIdentity = tuple[str, str]


class ResearchStrategyDirection(str, Enum):
    """Permitted directional interpretation of a research signal."""

    LONG_ONLY = "LONG_ONLY"
    SHORT_ONLY = "SHORT_ONLY"
    LONG_SHORT = "LONG_SHORT"


@dataclass(frozen=True)
class ResearchStrategyDefinition:
    """Versioned declarative strategy contract above research signals.

    A strategy definition states which versioned research signal it consumes and
    how signal scores are interpreted as long/short eligibility. It deliberately
    contains no portfolio weights, holdings, rebalance schedule, constraints,
    transaction costs, orders, or execution semantics.
    """

    strategy_key: str
    definition_version: str
    signal_identity: ResearchSignalIdentity
    direction: ResearchStrategyDirection
    long_threshold: float | None = None
    short_threshold: float | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_key, str) or not self.strategy_key.strip():
            raise InvalidInputError("Strategy key must be a non-empty string.")
        if not isinstance(self.definition_version, str) or not self.definition_version.strip():
            raise InvalidInputError("Strategy definition version must be a non-empty string.")

        signal_identity = self._normalize_signal_identity(self.signal_identity)
        direction = self._normalize_direction(self.direction)
        long_threshold = self._validate_threshold(self.long_threshold, "long_threshold")
        short_threshold = self._validate_threshold(self.short_threshold, "short_threshold")

        if direction is ResearchStrategyDirection.LONG_ONLY:
            if long_threshold is None:
                raise InvalidInputError("LONG_ONLY strategies require long_threshold.")
            if short_threshold is not None:
                raise InvalidInputError("LONG_ONLY strategies must not define short_threshold.")
        elif direction is ResearchStrategyDirection.SHORT_ONLY:
            if short_threshold is None:
                raise InvalidInputError("SHORT_ONLY strategies require short_threshold.")
            if long_threshold is not None:
                raise InvalidInputError("SHORT_ONLY strategies must not define long_threshold.")
        else:
            if long_threshold is None or short_threshold is None:
                raise InvalidInputError(
                    "LONG_SHORT strategies require both long_threshold and short_threshold."
                )
            if long_threshold <= short_threshold:
                raise InvalidInputError(
                    "LONG_SHORT long_threshold must be greater than short_threshold."
                )

        if self.description is not None and not isinstance(self.description, str):
            raise InvalidInputError("Strategy description must be a string or None.")

        object.__setattr__(self, "strategy_key", self.strategy_key.strip())
        object.__setattr__(self, "definition_version", self.definition_version.strip())
        object.__setattr__(self, "signal_identity", signal_identity)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "long_threshold", long_threshold)
        object.__setattr__(self, "short_threshold", short_threshold)
        if self.description is not None:
            object.__setattr__(self, "description", self.description.strip() or None)

    @staticmethod
    def _normalize_signal_identity(identity: ResearchSignalIdentity) -> ResearchSignalIdentity:
        if not isinstance(identity, tuple) or len(identity) != 2:
            raise InvalidInputError(
                "Strategy signal identity must be a (signal_key, definition_version) tuple."
            )
        signal_key, signal_version = identity
        if not isinstance(signal_key, str) or not isinstance(signal_version, str):
            raise InvalidInputError(
                "Strategy signal identity must contain string key and version values."
            )
        normalized = (signal_key.strip(), signal_version.strip())
        if not normalized[0] or not normalized[1]:
            raise InvalidInputError("Strategy signal identity values must not be empty.")
        return normalized

    @staticmethod
    def _normalize_direction(direction: ResearchStrategyDirection) -> ResearchStrategyDirection:
        if isinstance(direction, ResearchStrategyDirection):
            return direction
        try:
            return ResearchStrategyDirection(direction)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError("Strategy direction is invalid.") from exc

    @staticmethod
    def _validate_threshold(value: float | None, name: str) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise InvalidInputError(f"{name} must be a finite number within [0, 1].")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(f"{name} must be numeric or None.") from exc
        if not isfinite(numeric) or not 0.0 <= numeric <= 1.0:
            raise InvalidInputError(f"{name} must be finite and within [0, 1].")
        return numeric

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable strategy identity."""
        return self.strategy_key, self.definition_version


class ResearchStrategyDefinitionRegistry:
    """Resolve versioned strategy definitions without persistence."""

    def __init__(self, definitions: Iterable[ResearchStrategyDefinition] = ()):
        self._definitions: dict[tuple[str, str], ResearchStrategyDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ResearchStrategyDefinition) -> None:
        if not isinstance(definition, ResearchStrategyDefinition):
            raise InvalidInputError(
                "Research strategy registry accepts ResearchStrategyDefinition values."
            )
        if definition.identity in self._definitions:
            raise InvalidInputError(
                "Research strategy definition identity is already registered."
            )
        self._definitions[definition.identity] = definition

    def definitions(self) -> tuple[ResearchStrategyDefinition, ...]:
        """Return definitions in deterministic registration order."""
        return tuple(self._definitions.values())

    def get(self, strategy_key: str, definition_version: str) -> ResearchStrategyDefinition:
        if not isinstance(strategy_key, str) or not strategy_key.strip():
            raise InvalidInputError("Strategy key must be a non-empty string.")
        if not isinstance(definition_version, str) or not definition_version.strip():
            raise InvalidInputError("Strategy definition version must be a non-empty string.")
        key = (strategy_key.strip(), definition_version.strip())
        definition = self._definitions.get(key)
        if definition is None:
            raise ResourceNotFoundError(
                f"Research strategy definition not found: {key[0]} v{key[1]}"
            )
        return definition


class ResearchStrategyService:
    """Validate the versioned strategy-definition boundary."""

    @staticmethod
    def validate_definition(
        definition: ResearchStrategyDefinition,
    ) -> ResearchStrategyDefinition:
        if not isinstance(definition, ResearchStrategyDefinition):
            raise InvalidInputError(
                "Strategy validation requires a ResearchStrategyDefinition."
            )
        return definition
