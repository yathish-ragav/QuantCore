from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import (
    ResearchFactorComputationService,
    ResearchFactorValue,
)
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalDataset,
    ResearchHistoricalDatasetRow,
)


@dataclass(frozen=True)
class ResearchFactorPanelRow:
    """One factor value at one security/as-of point in a research panel."""

    symbol: str
    security_id: int
    as_of: datetime
    factor_value: ResearchFactorValue


@dataclass(frozen=True)
class ResearchFactorPanel:
    """Immutable cross-sectional panel for one versioned research factor."""

    factor_key: str
    definition_version: str
    rows: tuple[ResearchFactorPanelRow, ...]
    unit: str | None


class ResearchFactorPanelService:
    """Build deterministic cross-sectional factor panels from historical datasets."""

    def __init__(self, computation_service: ResearchFactorComputationService):
        if not isinstance(computation_service, ResearchFactorComputationService):
            raise InvalidInputError(
                "Research factor panels require a ResearchFactorComputationService."
            )
        self.computation_service = computation_service

    @staticmethod
    def _normalize_identity(factor_key: str, definition_version: str) -> tuple[str, str]:
        if not isinstance(factor_key, str) or not isinstance(definition_version, str):
            raise InvalidInputError("Factor identity must contain string values.")
        key = factor_key.strip()
        version = definition_version.strip()
        if not key:
            raise InvalidInputError("Factor key must not be empty.")
        if not version:
            raise InvalidInputError("Factor definition version must not be empty.")
        return key, version

    @staticmethod
    def _validate_historical_dataset(
        dataset: ResearchHistoricalDataset,
    ) -> tuple[ResearchHistoricalDatasetRow, ...]:
        if not isinstance(dataset, ResearchHistoricalDataset):
            raise InvalidInputError(
                "Research factor panels require a ResearchHistoricalDataset."
            )
        if not dataset.rows:
            raise InvalidInputError("Research historical dataset must not be empty.")

        seen: set[tuple[int, datetime]] = set()
        normalized_rows: list[ResearchHistoricalDatasetRow] = []
        for row in dataset.rows:
            if not isinstance(row, ResearchHistoricalDatasetRow):
                raise InvalidInputError(
                    "Research historical dataset rows must use the expected row contract."
                )
            symbol = row.symbol.strip().upper()
            if not symbol:
                raise InvalidInputError("Research historical row symbol must not be empty.")
            if not isinstance(row.security_id, int):
                raise InvalidInputError("Research historical row security_id must be an integer.")
            if not isinstance(row.as_of, datetime):
                raise InvalidInputError("Research historical row as_of must be a datetime.")
            as_of = row.as_of
            if as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
            if as_of > datetime.now(timezone.utc):
                raise InvalidInputError("As-of timestamp must not be in the future.")
            if row.feature_vector.symbol.strip().upper() != symbol:
                raise InvalidInputError(
                    "Research historical row symbol does not match its feature vector."
                )
            if row.feature_vector.security_id != row.security_id:
                raise InvalidInputError(
                    "Research historical row security_id does not match its feature vector."
                )
            if row.feature_vector.as_of != row.as_of:
                raise InvalidInputError(
                    "Research historical row as_of does not match its feature vector."
                )
            identity = (row.security_id, as_of)
            if identity in seen:
                raise InvalidInputError(
                    "Research historical dataset must not contain duplicate security/as-of rows."
                )
            seen.add(identity)
            normalized_rows.append(row)
        return tuple(normalized_rows)

    def build_factor_panel(
        self,
        dataset: ResearchHistoricalDataset,
        *,
        factor_key: str,
        definition_version: str,
    ) -> ResearchFactorPanel:
        """Compute one versioned factor across a deterministic historical panel.

        The service consumes only the feature vectors already present in the
        historical dataset. It does not read from the database, persist factor
        values, rank securities, normalize cross-sections, or construct signals.
        """
        normalized_identity = self._normalize_identity(factor_key, definition_version)
        rows = self._validate_historical_dataset(dataset)

        computed: list[ResearchFactorPanelRow] = []
        seen_factor_points: set[tuple[int, datetime]] = set()
        for row in rows:
            factor_value = self.computation_service.compute_factor(
                row.feature_vector,
                factor_key=normalized_identity[0],
                definition_version=normalized_identity[1],
            )
            point = (factor_value.security_id, factor_value.as_of)
            if point in seen_factor_points:
                raise InvalidInputError(
                    "Research factor panel must not contain duplicate security/as-of values."
                )
            seen_factor_points.add(point)
            computed.append(
                ResearchFactorPanelRow(
                    symbol=factor_value.symbol,
                    security_id=factor_value.security_id,
                    as_of=factor_value.as_of,
                    factor_value=factor_value,
                )
            )

        ordered = tuple(
            sorted(
                computed,
                key=lambda item: (item.as_of, item.symbol, item.security_id),
            )
        )
        units = {item.factor_value.unit for item in ordered}
        if len(units) != 1:
            raise InvalidInputError(
                "All factor values in a research panel must use one consistent unit."
            )

        return ResearchFactorPanel(
            factor_key=normalized_identity[0],
            definition_version=normalized_identity[1],
            rows=ordered,
            unit=next(iter(units)),
        )
