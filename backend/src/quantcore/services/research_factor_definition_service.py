from dataclasses import dataclass
from typing import Iterable

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError


ResearchFeatureIdentity = tuple[str, str]


@dataclass(frozen=True)
class ResearchFactorDefinition:
    """Versioned identity and input contract for a research factor.

    A factor definition describes which versioned research features are required
    and what kind of value the later factor-computation layer must produce. It
    intentionally contains no computation logic.
    """

    factor_key: str
    definition_version: str
    required_feature_identities: tuple[ResearchFeatureIdentity, ...]
    output_kind: str
    unit: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        factor_key = self.factor_key.strip()
        definition_version = self.definition_version.strip()
        output_kind = self.output_kind.strip().lower()

        if not factor_key:
            raise InvalidInputError("Factor key must not be empty.")
        if not definition_version:
            raise InvalidInputError("Factor definition version must not be empty.")
        if output_kind not in {"numeric", "text"}:
            raise InvalidInputError(
                "Factor output kind must be either 'numeric' or 'text'."
            )
        if self.unit is not None and not isinstance(self.unit, str):
            raise InvalidInputError("Factor unit must be a string or None.")
        if self.description is not None and not isinstance(self.description, str):
            raise InvalidInputError("Factor description must be a string or None.")

        identities = tuple(self.required_feature_identities)
        if not identities:
            raise InvalidInputError(
                "A research factor must require at least one feature identity."
            )

        normalized: list[ResearchFeatureIdentity] = []
        seen: set[ResearchFeatureIdentity] = set()
        for identity in identities:
            if not isinstance(identity, tuple) or len(identity) != 2:
                raise InvalidInputError(
                    "Feature identities must be (observation_key, definition_version) tuples."
                )
            observation_key, feature_version = identity
            if not isinstance(observation_key, str) or not isinstance(feature_version, str):
                raise InvalidInputError(
                    "Feature identities must contain string key and version values."
                )
            item = (observation_key.strip(), feature_version.strip())
            if not item[0]:
                raise InvalidInputError("Observation key must not be empty.")
            if not item[1]:
                raise InvalidInputError("Feature definition version must not be empty.")
            if item in seen:
                raise InvalidInputError(
                    "A research factor must not require duplicate feature identities."
                )
            seen.add(item)
            normalized.append(item)

        if output_kind == "text" and self.unit is not None:
            raise InvalidInputError("Text research factors must not declare a unit.")

        object.__setattr__(self, "factor_key", factor_key)
        object.__setattr__(self, "definition_version", definition_version)
        object.__setattr__(self, "required_feature_identities", tuple(normalized))
        object.__setattr__(self, "output_kind", output_kind)
        if self.unit is not None:
            object.__setattr__(self, "unit", self.unit.strip() or None)
        if self.description is not None:
            object.__setattr__(self, "description", self.description.strip() or None)

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable factor identity."""
        return self.factor_key, self.definition_version


class ResearchFactorDefinitionRegistry:
    """Resolve versioned factor definitions without persisting definitions."""

    def __init__(self, definitions: Iterable[ResearchFactorDefinition] = ()):
        self._definitions: dict[tuple[str, str], ResearchFactorDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ResearchFactorDefinition) -> None:
        if not isinstance(definition, ResearchFactorDefinition):
            raise InvalidInputError(
                "Research factor registry accepts ResearchFactorDefinition values."
            )
        if definition.identity in self._definitions:
            raise InvalidInputError(
                "Research factor definition identity is already registered."
            )
        self._definitions[definition.identity] = definition

    def definitions(self) -> tuple[ResearchFactorDefinition, ...]:
        """Return registered definitions in deterministic registration order."""
        return tuple(self._definitions.values())

    def get(
        self,
        factor_key: str,
        definition_version: str,
    ) -> ResearchFactorDefinition:
        key = factor_key.strip()
        version = definition_version.strip()
        if not key:
            raise InvalidInputError("Factor key must not be empty.")
        if not version:
            raise InvalidInputError("Factor definition version must not be empty.")
        definition = self._definitions.get((key, version))
        if definition is None:
            raise ResourceNotFoundError(
                f"Research factor definition not found: {key} v{version}"
            )
        return definition
