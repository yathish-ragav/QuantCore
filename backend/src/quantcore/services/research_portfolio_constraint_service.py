from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_construction_service import ResearchPortfolio


@dataclass(frozen=True)
class ResearchPortfolioConstraintDefinition:
    """Versioned declarative limits for validating a target research portfolio.

    Constraint values are expressed in portfolio-weight terms. Position and gross
    exposure limits are non-negative magnitudes. Net exposure limits are signed.
    A definition must configure at least one limit and cannot mutate portfolio
    weights; it only states the rules against which a target portfolio is checked.
    """

    constraint_key: str
    definition_version: str
    max_position_weight: float | None = None
    max_gross_exposure: float | None = None
    min_net_exposure: float | None = None
    max_net_exposure: float | None = None
    max_long_exposure: float | None = None
    max_short_exposure: float | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.constraint_key, str) or not self.constraint_key.strip():
            raise InvalidInputError("Constraint key must be a non-empty string.")
        if not isinstance(self.definition_version, str) or not self.definition_version.strip():
            raise InvalidInputError("Constraint definition version must be a non-empty string.")

        values = {
            "max_position_weight": self.max_position_weight,
            "max_gross_exposure": self.max_gross_exposure,
            "min_net_exposure": self.min_net_exposure,
            "max_net_exposure": self.max_net_exposure,
            "max_long_exposure": self.max_long_exposure,
            "max_short_exposure": self.max_short_exposure,
        }
        normalized = {
            name: self._validate_limit(value, name, non_negative=name not in {"min_net_exposure", "max_net_exposure"})
            for name, value in values.items()
        }
        if all(value is None for value in normalized.values()):
            raise InvalidInputError("At least one portfolio constraint must be configured.")

        min_net = normalized["min_net_exposure"]
        max_net = normalized["max_net_exposure"]
        if min_net is not None and max_net is not None and min_net > max_net:
            raise InvalidInputError("min_net_exposure must not exceed max_net_exposure.")

        if self.description is not None and not isinstance(self.description, str):
            raise InvalidInputError("Constraint description must be a string or None.")

        object.__setattr__(self, "constraint_key", self.constraint_key.strip())
        object.__setattr__(self, "definition_version", self.definition_version.strip())
        for name, value in normalized.items():
            object.__setattr__(self, name, value)
        if self.description is not None:
            object.__setattr__(self, "description", self.description.strip() or None)

    @staticmethod
    def _validate_limit(value: float | None, name: str, non_negative: bool) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise InvalidInputError(f"{name} must be a finite number.")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(f"{name} must be numeric or None.") from exc
        if not isfinite(numeric):
            raise InvalidInputError(f"{name} must be finite.")
        if non_negative and numeric < 0.0:
            raise InvalidInputError(f"{name} must be non-negative.")
        return numeric

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable constraint identity."""
        return self.constraint_key, self.definition_version


class ResearchPortfolioConstraintStatus(str, Enum):
    """Outcome of deterministic portfolio constraint validation."""

    PASSED = "PASSED"
    VIOLATED = "VIOLATED"


@dataclass(frozen=True)
class ResearchPortfolioConstraintViolation:
    """One deterministic portfolio constraint violation."""

    constraint: str
    observed_value: float
    limit: float


@dataclass(frozen=True)
class ResearchPortfolioConstraintResult:
    """Immutable validation result for one target portfolio."""

    constraint_key: str
    constraint_definition_version: str
    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    status: ResearchPortfolioConstraintStatus
    violations: tuple[ResearchPortfolioConstraintViolation, ...]
    observed_max_position_weight: float
    observed_gross_exposure: float
    observed_net_exposure: float
    observed_long_exposure: float
    observed_short_exposure: float


class ResearchPortfolioConstraintService:
    """Validate deterministic target portfolios against explicit constraints."""

    def validate(
        self,
        portfolio: ResearchPortfolio,
        definition: ResearchPortfolioConstraintDefinition,
    ) -> ResearchPortfolioConstraintResult:
        self._validate_inputs(portfolio, definition)

        max_position_weight = max(
            (abs(position.target_weight) for position in portfolio.positions),
            default=0.0,
        )
        gross_exposure = sum(abs(position.target_weight) for position in portfolio.positions)
        net_exposure = sum(position.target_weight for position in portfolio.positions)
        long_exposure = sum(
            position.target_weight for position in portfolio.positions if position.target_weight > 0.0
        )
        short_exposure = sum(
            abs(position.target_weight)
            for position in portfolio.positions
            if position.target_weight < 0.0
        )

        observed = (
            max_position_weight,
            gross_exposure,
            net_exposure,
            long_exposure,
            short_exposure,
        )
        if not all(isfinite(value) for value in observed):
            raise InvalidInputError("Portfolio exposure values must be finite.")

        violations: list[ResearchPortfolioConstraintViolation] = []
        if (
            definition.max_position_weight is not None
            and max_position_weight > definition.max_position_weight
        ):
            violations.append(
                ResearchPortfolioConstraintViolation(
                    "max_position_weight", max_position_weight, definition.max_position_weight
                )
            )
        if (
            definition.max_gross_exposure is not None
            and gross_exposure > definition.max_gross_exposure
        ):
            violations.append(
                ResearchPortfolioConstraintViolation(
                    "max_gross_exposure", gross_exposure, definition.max_gross_exposure
                )
            )
        if definition.min_net_exposure is not None and net_exposure < definition.min_net_exposure:
            violations.append(
                ResearchPortfolioConstraintViolation(
                    "min_net_exposure", net_exposure, definition.min_net_exposure
                )
            )
        if definition.max_net_exposure is not None and net_exposure > definition.max_net_exposure:
            violations.append(
                ResearchPortfolioConstraintViolation(
                    "max_net_exposure", net_exposure, definition.max_net_exposure
                )
            )
        if definition.max_long_exposure is not None and long_exposure > definition.max_long_exposure:
            violations.append(
                ResearchPortfolioConstraintViolation(
                    "max_long_exposure", long_exposure, definition.max_long_exposure
                )
            )
        if definition.max_short_exposure is not None and short_exposure > definition.max_short_exposure:
            violations.append(
                ResearchPortfolioConstraintViolation(
                    "max_short_exposure", short_exposure, definition.max_short_exposure
                )
            )

        return ResearchPortfolioConstraintResult(
            constraint_key=definition.constraint_key,
            constraint_definition_version=definition.definition_version,
            strategy_key=portfolio.strategy_key,
            strategy_definition_version=portfolio.strategy_definition_version,
            signal_identity=portfolio.signal_identity,
            as_of=portfolio.as_of,
            status=(
                ResearchPortfolioConstraintStatus.VIOLATED
                if violations
                else ResearchPortfolioConstraintStatus.PASSED
            ),
            violations=tuple(violations),
            observed_max_position_weight=max_position_weight,
            observed_gross_exposure=gross_exposure,
            observed_net_exposure=net_exposure,
            observed_long_exposure=long_exposure,
            observed_short_exposure=short_exposure,
        )

    @staticmethod
    def _validate_inputs(
        portfolio: ResearchPortfolio,
        definition: ResearchPortfolioConstraintDefinition,
    ) -> None:
        if not isinstance(portfolio, ResearchPortfolio):
            raise InvalidInputError(
                "Portfolio constraint validation requires a ResearchPortfolio."
            )
        if not isinstance(definition, ResearchPortfolioConstraintDefinition):
            raise InvalidInputError(
                "Portfolio constraint validation requires a ResearchPortfolioConstraintDefinition."
            )
        if not isinstance(portfolio.as_of, datetime) or portfolio.as_of.tzinfo is None:
            raise InvalidInputError("Portfolio constraint as_of must be timezone-aware.")
        if not isinstance(portfolio.positions, tuple):
            raise InvalidInputError("Portfolio positions must be an immutable tuple.")
        for position in portfolio.positions:
            if not isfinite(float(position.target_weight)):
                raise InvalidInputError("Portfolio target weights must be finite.")
