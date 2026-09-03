from dataclasses import dataclass
from datetime import datetime
from math import isclose, isfinite
from typing import Mapping

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)


ResearchFactorIdentity = tuple[str, str]


@dataclass(frozen=True)
class ResearchSignalDefinition:
    """Versioned identity and composition contract for a research signal.

    A research signal is a deterministic composite of rank-normalized research
    factors. Weights are explicit and must sum to one; the definition contains
    no portfolio, execution, or order-management semantics.
    """

    signal_key: str
    definition_version: str
    factor_identities: tuple[ResearchFactorIdentity, ...]
    weights: tuple[float, ...]
    description: str | None = None

    def __post_init__(self) -> None:
        signal_key = self.signal_key.strip()
        definition_version = self.definition_version.strip()
        if not signal_key:
            raise InvalidInputError("Signal key must not be empty.")
        if not definition_version:
            raise InvalidInputError("Signal definition version must not be empty.")

        identities = tuple(self.factor_identities)
        weights = tuple(self.weights)
        if not identities:
            raise InvalidInputError(
                "A research signal must require at least one factor identity."
            )
        if len(identities) != len(weights):
            raise InvalidInputError(
                "Research signal factor identities and weights must have the same length."
            )

        normalized: list[ResearchFactorIdentity] = []
        seen: set[ResearchFactorIdentity] = set()
        for identity in identities:
            if not isinstance(identity, tuple) or len(identity) != 2:
                raise InvalidInputError(
                    "Factor identities must be (factor_key, definition_version) tuples."
                )
            factor_key, factor_version = identity
            if not isinstance(factor_key, str) or not isinstance(factor_version, str):
                raise InvalidInputError(
                    "Factor identities must contain string key and version values."
                )
            item = (factor_key.strip(), factor_version.strip())
            if not item[0] or not item[1]:
                raise InvalidInputError(
                    "Factor identity key and definition version must not be empty."
                )
            if item in seen:
                raise InvalidInputError(
                    "A research signal must not contain duplicate factor identities."
                )
            seen.add(item)
            normalized.append(item)

        normalized_weights: list[float] = []
        for weight in weights:
            try:
                numeric_weight = float(weight)
            except (TypeError, ValueError) as exc:
                raise InvalidInputError("Research signal weights must be numeric.") from exc
            if not isfinite(numeric_weight) or numeric_weight <= 0.0:
                raise InvalidInputError(
                    "Research signal weights must be finite and strictly positive."
                )
            normalized_weights.append(numeric_weight)

        if not isclose(sum(normalized_weights), 1.0, rel_tol=1e-9, abs_tol=1e-9):
            raise InvalidInputError("Research signal weights must sum to 1.")

        object.__setattr__(self, "signal_key", signal_key)
        object.__setattr__(self, "definition_version", definition_version)
        object.__setattr__(self, "factor_identities", tuple(normalized))
        object.__setattr__(self, "weights", tuple(normalized_weights))
        if self.description is not None:
            if not isinstance(self.description, str):
                raise InvalidInputError("Signal description must be a string or None.")
            object.__setattr__(self, "description", self.description.strip() or None)

    @property
    def identity(self) -> tuple[str, str]:
        return self.signal_key, self.definition_version


@dataclass(frozen=True)
class ResearchSignalContribution:
    """One factor's weighted contribution to a composite research signal."""

    factor_key: str
    definition_version: str
    normalized_rank: float
    weight: float
    weighted_contribution: float


@dataclass(frozen=True)
class ResearchSignalRow:
    """One deterministic composite research signal at a security/as-of point."""

    symbol: str
    security_id: int
    as_of: datetime
    score: float
    centered_score: float
    contributions: tuple[ResearchSignalContribution, ...]


@dataclass(frozen=True)
class ResearchSignalPanel:
    """Immutable cross-sectional panel for one versioned research signal."""

    signal_key: str
    definition_version: str
    factor_identities: tuple[ResearchFactorIdentity, ...]
    rows: tuple[ResearchSignalRow, ...]
    construction: str


class ResearchSignalService:
    """Construct deterministic composite research signals from ranked factors.

    Each input factor must already be rank-normalized to [0, 1]. The service
    requires exact security/as-of alignment across all factors, so missing data
    cannot silently change the effective universe or weights. The composite
    score is the weighted average of normalized ranks and therefore remains in
    [0, 1]. ``centered_score`` maps that value to [-1, 1] for downstream research
    consumers. This service does not construct portfolios or orders.
    """

    CONSTRUCTION = "WEIGHTED_NORMALIZED_RANK_AVERAGE"

    def construct_signal(
        self,
        definition: ResearchSignalDefinition,
        panels_by_factor: Mapping[ResearchFactorIdentity, ResearchFactorRankedPanel],
    ) -> ResearchSignalPanel:
        self._validate_inputs(definition, panels_by_factor)

        first_identity = definition.factor_identities[0]
        first_panel = panels_by_factor[first_identity]
        rows_by_point: dict[tuple[int, datetime], list[ResearchFactorRankRow]] = {}
        for row in first_panel.rows:
            rows_by_point[(row.security_id, row.as_of)] = [row]

        for identity in definition.factor_identities[1:]:
            panel = panels_by_factor[identity]
            indexed = {(row.security_id, row.as_of): row for row in panel.rows}
            if set(indexed) != set(rows_by_point):
                raise InvalidInputError(
                    "Research signal factors must share the exact same security/as-of universe."
                )
            for point, rows in rows_by_point.items():
                rows.append(indexed[point])

        output: list[ResearchSignalRow] = []
        for point in sorted(rows_by_point, key=lambda item: (item[1], item[0])):
            factor_rows = rows_by_point[point]
            contributions: list[ResearchSignalContribution] = []
            score = 0.0
            for identity, weight, row in zip(
                definition.factor_identities,
                definition.weights,
                factor_rows,
            ):
                normalized_rank = float(row.normalized_rank)
                contribution = weight * normalized_rank
                score += contribution
                contributions.append(
                    ResearchSignalContribution(
                        factor_key=identity[0],
                        definition_version=identity[1],
                        normalized_rank=normalized_rank,
                        weight=weight,
                        weighted_contribution=contribution,
                    )
                )

            if not isfinite(score) or not 0.0 <= score <= 1.0:
                raise InvalidInputError(
                    "Research signal score must be finite and within [0, 1]."
                )
            centered_score = 2.0 * score - 1.0
            first_row = factor_rows[0]
            output.append(
                ResearchSignalRow(
                    symbol=first_row.symbol.strip().upper(),
                    security_id=first_row.security_id,
                    as_of=first_row.as_of,
                    score=score,
                    centered_score=centered_score,
                    contributions=tuple(contributions),
                )
            )

        return ResearchSignalPanel(
            signal_key=definition.signal_key,
            definition_version=definition.definition_version,
            factor_identities=definition.factor_identities,
            rows=tuple(output),
            construction=self.CONSTRUCTION,
        )

    @classmethod
    def _validate_inputs(
        cls,
        definition: ResearchSignalDefinition,
        panels_by_factor: Mapping[ResearchFactorIdentity, ResearchFactorRankedPanel],
    ) -> None:
        if not isinstance(definition, ResearchSignalDefinition):
            raise InvalidInputError(
                "Research signal construction requires a ResearchSignalDefinition."
            )
        if not isinstance(panels_by_factor, Mapping):
            raise InvalidInputError(
                "Research signal factor panels must be supplied as a mapping."
            )

        expected = set(definition.factor_identities)
        supplied = set(panels_by_factor)
        if supplied != expected:
            raise InvalidInputError(
                "Research signal panels must exactly match the factor identities in the definition."
            )

        expected_points: set[tuple[int, datetime]] | None = None
        for identity in definition.factor_identities:
            panel = panels_by_factor[identity]
            if not isinstance(panel, ResearchFactorRankedPanel):
                raise InvalidInputError(
                    "Research signal inputs must be ResearchFactorRankedPanel values."
                )
            if not panel.rows:
                raise InvalidInputError("Research signal factor panels must not be empty.")
            if (panel.factor_key, panel.definition_version) != identity:
                raise InvalidInputError(
                    "Research signal panel identity does not match its mapping key."
                )

            points: set[tuple[int, datetime]] = set()
            for row in panel.rows:
                if not isinstance(row, ResearchFactorRankRow):
                    raise InvalidInputError(
                        "Research signal panels must contain ResearchFactorRankRow values."
                    )
                if not isinstance(row.as_of, datetime) or row.as_of.tzinfo is None:
                    raise InvalidInputError("Research signal as_of must be timezone-aware.")
                if not isinstance(row.security_id, int):
                    raise InvalidInputError("Research signal security_id must be an integer.")
                point = (row.security_id, row.as_of)
                if point in points:
                    raise InvalidInputError(
                        "Research signal factor panels must not contain duplicate security/as-of points."
                    )
                points.add(point)

                if row.symbol.strip().upper() != row.factor_value.symbol.strip().upper():
                    raise InvalidInputError(
                        "Research signal row symbol does not match its factor value."
                    )
                if row.security_id != row.factor_value.security_id:
                    raise InvalidInputError(
                        "Research signal row security_id does not match its factor value."
                    )
                if row.as_of != row.factor_value.as_of:
                    raise InvalidInputError(
                        "Research signal row as_of does not match its factor value."
                    )
                if (row.factor_value.factor_key, row.factor_value.definition_version) != identity:
                    raise InvalidInputError(
                        "Research signal row factor identity does not match its panel identity."
                    )

                factor_rank = row.rank
                if not isinstance(factor_rank, (int, float)) or not isfinite(float(factor_rank)):
                    raise InvalidInputError("Research signal factor ranks must be finite.")
                if float(factor_rank) < 1.0:
                    raise InvalidInputError("Research signal factor ranks must be positive.")

                normalized_rank = row.normalized_rank
                if not isinstance(normalized_rank, (int, float)) or not isfinite(
                    float(normalized_rank)
                ):
                    raise InvalidInputError(
                        "Research signal normalized ranks must be finite."
                    )
                if not 0.0 <= float(normalized_rank) <= 1.0:
                    raise InvalidInputError(
                        "Research signal normalized ranks must be within [0, 1]."
                    )

            if expected_points is None:
                expected_points = points
            elif points != expected_points:
                raise InvalidInputError(
                    "Research signal factors must share the exact same security/as-of universe."
                )

        if not expected_points:
            raise InvalidInputError("Research signal factor panels must not be empty.")
