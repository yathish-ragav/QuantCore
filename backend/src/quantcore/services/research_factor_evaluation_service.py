from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from statistics import mean, median, pstdev

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)


@dataclass(frozen=True)
class ResearchFactorEvaluationSlice:
    """Descriptive cross-sectional diagnostics for one factor/as-of point."""

    as_of: datetime
    observation_count: int
    mean_value: float
    median_value: float
    stddev_value: float
    minimum_value: float
    maximum_value: float
    range_value: float


@dataclass(frozen=True)
class ResearchFactorEvaluation:
    """Immutable descriptive evaluation of a rank-normalized factor panel.

    This contract evaluates cross-sectional coverage and dispersion only. It
    intentionally does not measure forward returns, predictive performance,
    information coefficients, or factor returns; those require an explicit
    future-return contract and belong to later research layers.
    """

    factor_key: str
    definition_version: str
    cross_section_count: int
    total_observation_count: int
    minimum_cross_section_size: int
    maximum_cross_section_size: int
    mean_cross_section_size: float
    mean_cross_section_value: float
    mean_cross_section_stddev: float
    mean_cross_section_range: float
    cross_sections: tuple[ResearchFactorEvaluationSlice, ...]


class ResearchFactorEvaluationService:
    """Evaluate deterministic cross-sectional factor quality diagnostics."""

    def evaluate_ranked_panel(
        self,
        panel: ResearchFactorRankedPanel,
    ) -> ResearchFactorEvaluation:
        """Summarize factor coverage and dispersion independently per ``as_of``.

        Each cross-section is treated as a complete observed population, so
        ``stddev_value`` uses population standard deviation. The service consumes
        an already rank-normalized panel and never reads persistence, computes
        factor values, estimates future returns, or constructs signals.
        """
        self._validate_panel(panel)

        by_as_of: dict[datetime, list[ResearchFactorRankRow]] = {}
        for row in panel.rows:
            by_as_of.setdefault(row.as_of, []).append(row)

        slices: list[ResearchFactorEvaluationSlice] = []
        for as_of in sorted(by_as_of):
            values = [float(row.factor_value.value_numeric) for row in by_as_of[as_of]]
            minimum = min(values)
            maximum = max(values)
            slices.append(
                ResearchFactorEvaluationSlice(
                    as_of=as_of,
                    observation_count=len(values),
                    mean_value=mean(values),
                    median_value=median(values),
                    stddev_value=pstdev(values),
                    minimum_value=minimum,
                    maximum_value=maximum,
                    range_value=maximum - minimum,
                )
            )

        sizes = [item.observation_count for item in slices]
        return ResearchFactorEvaluation(
            factor_key=panel.factor_key,
            definition_version=panel.definition_version,
            cross_section_count=len(slices),
            total_observation_count=sum(sizes),
            minimum_cross_section_size=min(sizes),
            maximum_cross_section_size=max(sizes),
            mean_cross_section_size=mean(sizes),
            mean_cross_section_value=mean(item.mean_value for item in slices),
            mean_cross_section_stddev=mean(item.stddev_value for item in slices),
            mean_cross_section_range=mean(item.range_value for item in slices),
            cross_sections=tuple(slices),
        )

    @staticmethod
    def _validate_panel(panel: ResearchFactorRankedPanel) -> None:
        if not isinstance(panel, ResearchFactorRankedPanel):
            raise InvalidInputError(
                "Factor evaluation requires a ResearchFactorRankedPanel."
            )
        if not panel.rows:
            raise InvalidInputError("Research factor ranked panel must not be empty.")
        if not isinstance(panel.factor_key, str) or not panel.factor_key.strip():
            raise InvalidInputError("Research factor evaluation requires a factor key.")
        if (
            not isinstance(panel.definition_version, str)
            or not panel.definition_version.strip()
        ):
            raise InvalidInputError(
                "Research factor evaluation requires a definition version."
            )

        seen: set[tuple[int, datetime]] = set()
        for row in panel.rows:
            if not isinstance(row, ResearchFactorRankRow):
                raise InvalidInputError(
                    "Research factor evaluation rows must use the expected row contract."
                )
            if not isinstance(row.as_of, datetime) or row.as_of.tzinfo is None:
                raise InvalidInputError(
                    "Research factor evaluation row as_of must be timezone-aware."
                )
            if not isinstance(row.security_id, int):
                raise InvalidInputError(
                    "Research factor evaluation row security_id must be an integer."
                )
            if not isinstance(row.factor_value, ResearchFactorValue):
                raise InvalidInputError(
                    "Research factor evaluation requires valid research factor values."
                )
            if (
                row.factor_value.factor_key != panel.factor_key
                or row.factor_value.definition_version != panel.definition_version
            ):
                raise InvalidInputError(
                    "Research factor evaluation row factor identity does not match the panel."
                )
            if row.factor_value.symbol.strip().upper() != row.symbol.strip().upper():
                raise InvalidInputError(
                    "Research factor evaluation row symbol does not match its factor value."
                )
            if row.factor_value.security_id != row.security_id:
                raise InvalidInputError(
                    "Research factor evaluation row security_id does not match its factor value."
                )
            if row.factor_value.as_of != row.as_of:
                raise InvalidInputError(
                    "Research factor evaluation row as_of does not match its factor value."
                )
            value = row.factor_value.value_numeric
            if value is None:
                raise InvalidInputError(
                    "Research factor evaluation requires numeric factor values."
                )
            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise InvalidInputError(
                    "Research factor evaluation requires numeric factor values."
                ) from exc
            if not isfinite(numeric_value):
                raise InvalidInputError(
                    "Research factor evaluation requires finite factor values."
                )
            if not isinstance(row.rank, (int, float)) or not isfinite(float(row.rank)):
                raise InvalidInputError("Research factor evaluation ranks must be finite.")
            if float(row.rank) < 1.0:
                raise InvalidInputError("Research factor evaluation ranks must be positive.")
            if not isinstance(row.normalized_rank, (int, float)) or not isfinite(
                float(row.normalized_rank)
            ):
                raise InvalidInputError(
                    "Research factor evaluation normalized ranks must be finite."
                )
            if not 0.0 <= float(row.normalized_rank) <= 1.0:
                raise InvalidInputError(
                    "Research factor evaluation normalized ranks must be within [0, 1]."
                )

            point = (row.security_id, row.as_of)
            if point in seen:
                raise InvalidInputError(
                    "Research factor ranked panel must not contain duplicate security/as-of points."
                )
            seen.add(point)
