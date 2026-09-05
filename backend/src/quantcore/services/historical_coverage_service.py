from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

from quantcore.core.exceptions import InvalidInputError
from typing import Iterable


class HistoricalCoverageStatus(str, Enum):
    """Deterministic historical coverage state for one requested interval."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_OBSERVATIONS = "NO_OBSERVATIONS"
    NO_EXPECTED_OBSERVATIONS = "NO_EXPECTED_OBSERVATIONS"


@dataclass(frozen=True)
class HistoricalCoverageResult:
    """Coverage and continuity diagnostics for a supplied observation schedule.

    ``expected_dates`` is the authoritative schedule for the dataset. The
    service intentionally does not assume that every calendar day is a valid
    observation day; callers should supply a dataset-appropriate schedule
    (for example, an exchange trading calendar).
    """

    start_at: datetime
    end_at: datetime
    expected_count: int
    observed_count: int
    missing_count: int
    coverage_ratio: float
    status: HistoricalCoverageStatus
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    missing_dates: tuple[datetime, ...]
    gap_count: int
    max_gap_observations: int

    @property
    def is_complete(self) -> bool:
        return self.status is HistoricalCoverageStatus.COMPLETE

    @property
    def has_gaps(self) -> bool:
        return self.missing_count > 0


class HistoricalCoverageService:
    """Measure historical observation coverage without mutating source data.

    The service is deliberately schedule-driven. A market calendar, filing
    schedule, or other dataset-specific policy belongs outside this service.
    This keeps continuity semantics deterministic and prevents weekends,
    holidays, filing cadence, or other legitimate non-observation periods from
    being mislabeled as missing data.
    """

    def assess(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        expected_dates: Iterable[datetime],
        observed_dates: Iterable[datetime],
    ) -> HistoricalCoverageResult:
        self._validate_boundary(start_at, end_at)

        expected = self._normalize_expected(
            expected_dates,
            start_at=start_at,
            end_at=end_at,
        )
        observed = self._normalize_observed(
            observed_dates,
            start_at=start_at,
            end_at=end_at,
        )

        if not expected:
            return HistoricalCoverageResult(
                start_at=start_at,
                end_at=end_at,
                expected_count=0,
                observed_count=0,
                missing_count=0,
                coverage_ratio=0.0,
                status=HistoricalCoverageStatus.NO_EXPECTED_OBSERVATIONS,
                first_observed_at=None,
                last_observed_at=None,
                missing_dates=(),
                gap_count=0,
                max_gap_observations=0,
            )

        expected_set = set(expected)
        unexpected = tuple(date for date in observed if date not in expected_set)
        if unexpected:
            raise InvalidInputError(
                "Historical coverage observed_dates contain timestamps that are "
                "not present in the expected observation schedule."
            )

        observed_in_schedule = observed
        observed_set = set(observed_in_schedule)
        missing = tuple(date for date in expected if date not in observed_set)

        observed_count = len(observed_in_schedule)
        missing_count = len(missing)
        coverage_ratio = observed_count / len(expected)

        if not isfinite(coverage_ratio):
            raise InvalidInputError("Historical coverage ratio must be finite.")

        if observed_count == 0:
            status = HistoricalCoverageStatus.NO_OBSERVATIONS
        elif missing_count == 0:
            status = HistoricalCoverageStatus.COMPLETE
        else:
            status = HistoricalCoverageStatus.PARTIAL

        return HistoricalCoverageResult(
            start_at=start_at,
            end_at=end_at,
            expected_count=len(expected),
            observed_count=observed_count,
            missing_count=missing_count,
            coverage_ratio=coverage_ratio,
            status=status,
            first_observed_at=observed_in_schedule[0] if observed_in_schedule else None,
            last_observed_at=observed_in_schedule[-1] if observed_in_schedule else None,
            missing_dates=missing,
            gap_count=self._gap_count(missing, expected),
            max_gap_observations=self._max_gap(missing, expected),
        )

    @staticmethod
    def _validate_boundary(start_at: datetime, end_at: datetime) -> None:
        if not isinstance(start_at, datetime) or start_at.tzinfo is None:
            raise InvalidInputError("Historical coverage start_at must be timezone-aware.")
        if not isinstance(end_at, datetime) or end_at.tzinfo is None:
            raise InvalidInputError("Historical coverage end_at must be timezone-aware.")
        if end_at < start_at:
            raise InvalidInputError("Historical coverage end_at must not precede start_at.")

    @classmethod
    def _normalize_expected(
        cls,
        dates: Iterable[datetime],
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[datetime, ...]:
        values = cls._normalize_dates(dates, "expected")
        for date in values:
            cls._validate_in_range(date, start_at, end_at, "expected")
        return tuple(sorted(values))

    @classmethod
    def _normalize_observed(
        cls,
        dates: Iterable[datetime],
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[datetime, ...]:
        values = cls._normalize_dates(dates, "observed")
        for date in values:
            cls._validate_in_range(date, start_at, end_at, "observed")
        return tuple(sorted(values))

    @staticmethod
    def _normalize_dates(
        dates: Iterable[datetime],
        label: str,
    ) -> list[datetime]:
        try:
            values = list(dates)
        except TypeError as exc:
            raise InvalidInputError(
                f"Historical coverage {label}_dates must be iterable."
            ) from exc

        normalized: list[datetime] = []
        seen: set[datetime] = set()
        for date in values:
            if not isinstance(date, datetime) or date.tzinfo is None:
                raise InvalidInputError(
                    f"Historical coverage {label}_dates must contain timezone-aware datetimes."
                )
            if date in seen:
                raise InvalidInputError(
                    f"Historical coverage {label}_dates contain duplicate timestamps."
                )
            seen.add(date)
            normalized.append(date)
        return normalized

    @staticmethod
    def _validate_in_range(
        date: datetime,
        start_at: datetime,
        end_at: datetime,
        label: str,
    ) -> None:
        if date < start_at or date > end_at:
            raise InvalidInputError(
                f"Historical coverage {label} observation {date.isoformat()} "
                f"is outside the requested interval."
            )

    @staticmethod
    def _gap_count(
        missing: tuple[datetime, ...],
        expected: tuple[datetime, ...],
    ) -> int:
        if not missing:
            return 0
        expected_index = {date: index for index, date in enumerate(expected)}
        gaps = 1
        for previous, current in zip(missing, missing[1:]):
            if expected_index[current] != expected_index[previous] + 1:
                gaps += 1
        return gaps

    @staticmethod
    def _max_gap(
        missing: tuple[datetime, ...],
        expected: tuple[datetime, ...],
    ) -> int:
        if not missing:
            return 0
        expected_index = {date: index for index, date in enumerate(expected)}
        maximum = 1
        current = 1
        for previous, value in zip(missing, missing[1:]):
            if expected_index[value] == expected_index[previous] + 1:
                current += 1
                maximum = max(maximum, current)
            else:
                current = 1
        return maximum
