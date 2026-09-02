from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Iterable

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_panel_service import (
    ResearchFactorPanel,
    ResearchFactorPanelRow,
)


@dataclass(frozen=True)
class ResearchFactorRankRow:
    """One cross-sectional rank for one factor/security/as-of point."""

    symbol: str
    security_id: int
    as_of: datetime
    factor_value: ResearchFactorValue
    rank: float
    normalized_rank: float


@dataclass(frozen=True)
class ResearchFactorRankedPanel:
    """Immutable cross-sectional rank-normalized representation of one factor."""

    factor_key: str
    definition_version: str
    rows: tuple[ResearchFactorRankRow, ...]
    ranking: str
    higher_is_better: bool


class ResearchFactorCrossSectionalService:
    """Apply deterministic cross-sectional rank normalization to a factor panel."""

    def rank_factor_panel(
        self,
        panel: ResearchFactorPanel,
        *,
        higher_is_better: bool = True,
    ) -> ResearchFactorRankedPanel:
        """Rank numeric factor values independently within each ``as_of`` cross-section.

        Ranks use the competition-free average-tie convention: tied observations
        receive the arithmetic mean of their occupied 1-based ranks. With
        ``higher_is_better=True`` the largest factor value receives rank 1.

        ``normalized_rank`` maps the best value to 1 and the worst value to 0.
        A singleton cross-section receives 0.5 because no relative ordering is
        identifiable from one observation.
        """
        self._validate_panel(panel)
        if not isinstance(higher_is_better, bool):
            raise InvalidInputError("higher_is_better must be a boolean.")

        by_as_of: dict[datetime, list[ResearchFactorPanelRow]] = {}
        for row in panel.rows:
            factor_value = row.factor_value
            if not isinstance(factor_value, ResearchFactorValue):
                raise InvalidInputError(
                    "Cross-sectional ranking requires valid research factor values."
                )
            value = factor_value.value_numeric
            if value is None:
                raise InvalidInputError(
                    "Cross-sectional ranking requires numeric factor values."
                )
            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise InvalidInputError(
                    "Cross-sectional ranking requires numeric factor values."
                ) from exc
            if not isfinite(numeric_value):
                raise InvalidInputError(
                    "Cross-sectional ranking requires finite factor values."
                )
            by_as_of.setdefault(row.as_of, []).append(row)

        ranked: list[ResearchFactorRankRow] = []
        for as_of in sorted(by_as_of):
            cross_section = by_as_of[as_of]
            ordered = sorted(
                cross_section,
                key=lambda row: (
                    -float(row.factor_value.value_numeric)
                    if higher_is_better
                    else float(row.factor_value.value_numeric),
                    row.symbol,
                    row.security_id,
                ),
            )
            ranks = self._average_tie_ranks(ordered)
            size = len(ordered)
            for index, row in enumerate(ordered):
                numeric_value = float(row.factor_value.value_numeric)
                rank = ranks[index]
                normalized = 0.5 if size == 1 else (size - rank) / (size - 1)
                ranked.append(
                    ResearchFactorRankRow(
                        symbol=row.symbol.strip().upper(),
                        security_id=row.security_id,
                        as_of=as_of,
                        factor_value=row.factor_value,
                        rank=rank,
                        normalized_rank=normalized,
                    )
                )

        rows = tuple(
            sorted(
                ranked,
                key=lambda row: (row.as_of, row.rank, row.symbol, row.security_id),
            )
        )
        return ResearchFactorRankedPanel(
            factor_key=panel.factor_key,
            definition_version=panel.definition_version,
            rows=rows,
            ranking="average_tie",
            higher_is_better=higher_is_better,
        )

    @staticmethod
    def _validate_panel(panel: ResearchFactorPanel) -> None:
        if not isinstance(panel, ResearchFactorPanel):
            raise InvalidInputError(
                "Cross-sectional analysis requires a ResearchFactorPanel."
            )
        if not panel.rows:
            raise InvalidInputError("Research factor panel must not be empty.")

        seen: set[tuple[int, datetime]] = set()
        for row in panel.rows:
            if not isinstance(row, ResearchFactorPanelRow):
                raise InvalidInputError(
                    "Research factor panel rows must use the expected row contract."
                )
            if not isinstance(row.as_of, datetime) or row.as_of.tzinfo is None:
                raise InvalidInputError(
                    "Research factor panel row as_of must be timezone-aware."
                )
            if not isinstance(row.security_id, int):
                raise InvalidInputError(
                    "Research factor panel row security_id must be an integer."
                )
            point = (row.security_id, row.as_of)
            if point in seen:
                raise InvalidInputError(
                    "Research factor panel must not contain duplicate "
                    "security/as-of points."
                )
            seen.add(point)

    @staticmethod
    def _average_tie_ranks(
        ordered: Iterable[ResearchFactorPanelRow],
    ) -> tuple[float, ...]:
        rows = tuple(ordered)
        ranks: list[float] = [0.0] * len(rows)
        start = 0
        while start < len(rows):
            value = float(rows[start].factor_value.value_numeric)
            end = start + 1
            while (
                end < len(rows)
                and float(rows[end].factor_value.value_numeric) == value
            ):
                end += 1
            average_rank = (start + 1 + end) / 2.0
            for index in range(start, end):
                ranks[index] = average_rank
            start = end
        return tuple(ranks)
