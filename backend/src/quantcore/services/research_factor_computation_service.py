from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable, Mapping, Protocol

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.research_dataset_service import ResearchFeatureVector
from quantcore.services.research_factor_definition_service import (
    ResearchFactorDefinition,
    ResearchFactorDefinitionRegistry,
    ResearchFeatureIdentity,
)


@dataclass(frozen=True)
class ResearchFactorValue:
    """One deterministic, non-persisted factor value for a PIT feature vector."""

    factor_key: str
    definition_version: str
    symbol: str
    security_id: int
    as_of: datetime
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    input_manifest: Mapping | None = None


class ResearchFactorCalculator(Protocol):
    """Contract for deterministic computation from one research feature vector."""

    @property
    def factor_key(self) -> str: ...

    @property
    def definition_version(self) -> str: ...

    def compute(
        self,
        feature_vector: ResearchFeatureVector,
        definition: ResearchFactorDefinition,
    ) -> ResearchFactorValue: ...


class ResearchFactorCalculatorRegistry:
    """Resolve versioned factor calculators without persisting calculators."""

    def __init__(self, calculators: Iterable[ResearchFactorCalculator] = ()):
        self._calculators: dict[
            tuple[str, str], ResearchFactorCalculator
        ] = {}
        for calculator in calculators:
            self.register(calculator)

    @staticmethod
    def _identity(calculator: ResearchFactorCalculator) -> tuple[str, str]:
        try:
            key = calculator.factor_key
            version = calculator.definition_version
        except AttributeError as exc:
            raise InvalidInputError(
                "Research factor calculators must expose factor_key and definition_version."
            ) from exc

        if not isinstance(key, str) or not isinstance(version, str):
            raise InvalidInputError(
                "Research factor calculator identity must contain string values."
            )
        key = key.strip()
        version = version.strip()
        if not key:
            raise InvalidInputError("Factor key must not be empty.")
        if not version:
            raise InvalidInputError("Factor definition version must not be empty.")
        return key, version

    def register(self, calculator: ResearchFactorCalculator) -> None:
        identity = self._identity(calculator)
        if identity in self._calculators:
            raise InvalidInputError(
                "Research factor calculator identity is already registered."
            )
        self._calculators[identity] = calculator

    def calculators(self) -> tuple[ResearchFactorCalculator, ...]:
        """Return registered calculators in deterministic registration order."""
        return tuple(self._calculators.values())

    def get(
        self,
        factor_key: str,
        definition_version: str,
    ) -> ResearchFactorCalculator:
        key = factor_key.strip()
        version = definition_version.strip()
        if not key:
            raise InvalidInputError("Factor key must not be empty.")
        if not version:
            raise InvalidInputError("Factor definition version must not be empty.")

        calculator = self._calculators.get((key, version))
        if calculator is None:
            raise ResourceNotFoundError(
                f"Research factor calculator not found: {key} v{version}"
            )
        return calculator


class ResearchFactorComputationService:
    """Compute versioned research factors from already-built PIT feature vectors."""

    def __init__(
        self,
        definitions: Iterable[ResearchFactorDefinition],
        calculators: Iterable[ResearchFactorCalculator],
    ):
        self.definition_registry = ResearchFactorDefinitionRegistry(definitions)
        self.calculator_registry = ResearchFactorCalculatorRegistry(calculators)
        self._validate_registry_alignment()

    def _validate_registry_alignment(self) -> None:
        calculator_identities = {
            (calculator.factor_key.strip(), calculator.definition_version.strip())
            for calculator in self.calculator_registry.calculators()
        }
        for definition in self.definition_registry.definitions():
            if definition.identity not in calculator_identities:
                raise ResourceNotFoundError(
                    "No calculator registered for research factor definition: "
                    f"{definition.factor_key} v{definition.definition_version}"
                )

    @staticmethod
    def _normalize_feature_identities(
        feature_vector: ResearchFeatureVector,
    ) -> tuple[ResearchFeatureIdentity, ...]:
        identities: list[ResearchFeatureIdentity] = []
        seen: set[ResearchFeatureIdentity] = set()
        for feature in feature_vector.features:
            identity = (
                feature.observation_key.strip(),
                feature.definition_version.strip(),
            )
            if not identity[0] or not identity[1]:
                raise InvalidInputError(
                    "Research feature identities must not be empty."
                )
            if identity in seen:
                raise InvalidInputError(
                    "Research feature vector must not contain duplicate feature identities."
                )
            seen.add(identity)
            identities.append(identity)
        return tuple(identities)

    @staticmethod
    def _validate_feature_vector(
        feature_vector: ResearchFeatureVector,
        definition: ResearchFactorDefinition,
    ) -> tuple[ResearchFeatureIdentity, ...]:
        if not isinstance(feature_vector, ResearchFeatureVector):
            raise InvalidInputError(
                "Research factor computation requires a ResearchFeatureVector."
            )

        symbol = feature_vector.symbol.strip().upper()
        if not symbol:
            raise InvalidInputError("Research feature-vector symbol must not be empty.")

        if not isinstance(feature_vector.security_id, int):
            raise InvalidInputError("Research feature-vector security_id must be an integer.")

        as_of = feature_vector.as_of
        if not isinstance(as_of, datetime):
            raise InvalidInputError("Research feature-vector as_of must be a datetime.")
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        if as_of > datetime.now(timezone.utc):
            raise InvalidInputError("As-of timestamp must not be in the future.")

        identities = ResearchFactorComputationService._normalize_feature_identities(
            feature_vector
        )
        if identities != definition.required_feature_identities:
            raise InvalidInputError(
                "Research feature vector does not match the factor definition's "
                "required feature identities and order."
            )

        for feature in feature_vector.features:
            if feature.observation_as_of.tzinfo is None:
                raise InvalidInputError(
                    "Research feature observation timestamps must be timezone-aware."
                )
            if feature.observation_as_of > as_of:
                raise InvalidInputError(
                    "Research feature observation exceeds the requested as-of boundary."
                )
            if feature.value_numeric is not None and feature.value_text is not None:
                raise InvalidInputError(
                    "A research feature must contain either a numeric or text value."
                )
            if feature.value_numeric is None and feature.value_text is None:
                raise InvalidInputError("A research feature must contain a value.")
        return identities

    @staticmethod
    def _validate_result(
        result: ResearchFactorValue,
        feature_vector: ResearchFeatureVector,
        definition: ResearchFactorDefinition,
    ) -> None:
        if not isinstance(result, ResearchFactorValue):
            raise InvalidInputError(
                "Research factor calculators must return ResearchFactorValue."
            )

        if (result.factor_key.strip(), result.definition_version.strip()) != definition.identity:
            raise InvalidInputError(
                "Research factor result identity does not match its definition."
            )

        if result.symbol.strip().upper() != feature_vector.symbol.strip().upper():
            raise InvalidInputError(
                "Research factor result symbol does not match the feature vector."
            )

        if result.security_id != feature_vector.security_id:
            raise InvalidInputError(
                "Research factor result security_id does not match the feature vector."
            )

        if result.as_of != feature_vector.as_of:
            raise InvalidInputError(
                "Research factor result as_of does not match the feature vector."
            )

        if result.value_numeric is None and result.value_text is None:
            raise InvalidInputError("A research factor must produce a value.")
        if result.value_numeric is not None and result.value_text is not None:
            raise InvalidInputError(
                "A research factor must produce either a numeric or text value."
            )

        if definition.output_kind == "numeric":
            if result.value_numeric is None:
                raise InvalidInputError(
                    "Numeric research factors must produce a numeric value."
                )
            if not isfinite(float(result.value_numeric)):
                raise InvalidInputError(
                    "Numeric research factor values must be finite."
                )
        elif result.value_text is None:
            raise InvalidInputError("Text research factors must produce a text value.")

        if definition.unit != result.unit:
            raise InvalidInputError(
                "Research factor result unit does not match its definition."
            )

    @staticmethod
    def _build_manifest(
        result: ResearchFactorValue,
        feature_vector: ResearchFeatureVector,
        definition: ResearchFactorDefinition,
    ) -> dict:
        inputs = tuple(
            {
                "observation_key": feature.observation_key.strip(),
                "definition_version": feature.definition_version.strip(),
                "observation_as_of": feature.observation_as_of.isoformat(),
                "input_fingerprint": feature.input_fingerprint,
                "input_manifest": dict(feature.input_manifest),
            }
            for feature in feature_vector.features
        )

        return {
            "factor": {
                "factor_key": definition.factor_key,
                "definition_version": definition.definition_version,
            },
            "pit_dataset": {
                "symbol": feature_vector.symbol.strip().upper(),
                "security_id": feature_vector.security_id,
                "as_of": feature_vector.as_of.isoformat(),
            },
            "inputs": inputs,
            "calculation": dict(result.input_manifest or {}),
        }

    def compute_factor(
        self,
        feature_vector: ResearchFeatureVector,
        *,
        factor_key: str,
        definition_version: str,
    ) -> ResearchFactorValue:
        """Compute one versioned factor from one already-materialized PIT vector.

        This method consumes a feature vector only. It does not read from the
        database, compute observations, persist factors, rank securities, or
        construct portfolios.
        """
        definition = self.definition_registry.get(factor_key, definition_version)
        self._validate_feature_vector(feature_vector, definition)

        calculator = self.calculator_registry.get(
            definition.factor_key,
            definition.definition_version,
        )
        result = calculator.compute(feature_vector, definition)
        self._validate_result(result, feature_vector, definition)

        return ResearchFactorValue(
            factor_key=definition.factor_key,
            definition_version=definition.definition_version,
            symbol=feature_vector.symbol.strip().upper(),
            security_id=feature_vector.security_id,
            as_of=feature_vector.as_of,
            value_numeric=result.value_numeric,
            value_text=result.value_text,
            unit=result.unit,
            input_manifest=self._build_manifest(
                result,
                feature_vector,
                definition,
            ),
        )
