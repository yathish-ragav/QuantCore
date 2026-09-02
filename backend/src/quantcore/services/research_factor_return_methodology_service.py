from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from statistics import mean

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_return_service import (
    ResearchFactorReturnPanel,
    ResearchFactorReturnRow,
)


@dataclass(frozen=True)
class ResearchFactorReturnBucket:
    """One rank-ordered, equal-weighted bucket for one factor/as-of point."""

    bucket_number: int
    observation_count: int
    eligible_return_count: int
    mean_forward_return: float | None


@dataclass(frozen=True)
class ResearchFactorReturnSlice:
    """One cross-sectional factor-return observation at one factor/as-of point."""

    as_of: datetime
    total_observation_count: int
    eligible_observation_count: int
    long_bucket: int
    short_bucket: int
    long_return: float | None
    short_return: float | None
    long_short_return: float | None
    status: str
    buckets: tuple[ResearchFactorReturnBucket, ...]


@dataclass(frozen=True)
class ResearchFactorReturnSeries:
    """Immutable cross-sectional factor-return series."""

    factor_key: str
    definition_version: str
    horizon: int
    return_price_basis: PriceBasis
    bucket_count: int
    weighting: str
    long_bucket: int
    short_bucket: int
    construction: str
    slices: tuple[ResearchFactorReturnSlice, ...]


class ResearchFactorReturnMethodologyService:
    """Construct deterministic factor returns from aligned forward outcomes.

    The methodology is deliberately explicit: rank-ordered buckets are formed
    from the factor panel before unavailable future returns are excluded. Each
    bucket is equal-weighted, the best-ranked bucket is long, the worst-ranked
    bucket is short, and the factor return is long minus short.
    """

    WEIGHTING = "EQUAL_WEIGHTED"
    CONSTRUCTION = "RANK_ORDERED_BUCKET_LONG_SHORT"
    STATUS_AVAILABLE = "AVAILABLE"
    STATUS_INSUFFICIENT_LONG = "INSUFFICIENT_LONG_RETURN_OBSERVATIONS"
    STATUS_INSUFFICIENT_SHORT = "INSUFFICIENT_SHORT_RETURN_OBSERVATIONS"
    STATUS_NO_ELIGIBLE_RETURNS = "NO_ELIGIBLE_RETURNS"

    def compute_factor_return_series(
        self,
        panel: ResearchFactorReturnPanel,
        *,
        bucket_count: int = 5,
        minimum_observations_per_leg: int = 1,
    ) -> ResearchFactorReturnSeries:
        """Compute rank-sorted equal-weighted long/short factor returns.

        Bucket membership is determined from the factor ranking already present
        in ``panel``. Future-return availability therefore cannot change which
        securities belong to a bucket. Unavailable outcome rows remain in their
        original buckets but do not contribute to that bucket's realized return.

        Buckets are distributed as evenly as possible by deterministic rank order;
        earlier buckets receive the remainder when the panel size is not divisible
        by ``bucket_count``. The first bucket is the long leg and the last bucket
        is the short leg because rank 1 represents the best factor exposure.
        """
        self._validate_inputs(panel, bucket_count, minimum_observations_per_leg)

        grouped: dict[datetime, list[ResearchFactorReturnRow]] = {}
        for row in panel.rows:
            grouped.setdefault(row.factor_as_of, []).append(row)

        slices: list[ResearchFactorReturnSlice] = []
        for as_of in sorted(grouped):
            ordered = sorted(
                grouped[as_of],
                key=lambda row: (row.factor_rank, row.symbol, row.security_id),
            )
            assignments = self._assign_buckets(ordered, bucket_count)
            buckets: list[ResearchFactorReturnBucket] = []

            for bucket_number in range(1, bucket_count + 1):
                members = [
                    row for row, assigned in assignments if assigned == bucket_number
                ]
                returns = [
                    float(row.forward_return)
                    for row in members
                    if row.status == "AVAILABLE" and row.forward_return is not None
                ]
                buckets.append(
                    ResearchFactorReturnBucket(
                        bucket_number=bucket_number,
                        observation_count=len(members),
                        eligible_return_count=len(returns),
                        mean_forward_return=mean(returns) if returns else None,
                    )
                )

            long_bucket = buckets[0]
            short_bucket = buckets[-1]
            long_return = long_bucket.mean_forward_return
            short_return = short_bucket.mean_forward_return
            eligible_count = sum(bucket.eligible_return_count for bucket in buckets)

            if eligible_count == 0:
                status = self.STATUS_NO_ELIGIBLE_RETURNS
                spread = None
            elif long_bucket.eligible_return_count < minimum_observations_per_leg:
                status = self.STATUS_INSUFFICIENT_LONG
                spread = None
            elif short_bucket.eligible_return_count < minimum_observations_per_leg:
                status = self.STATUS_INSUFFICIENT_SHORT
                spread = None
            else:
                status = self.STATUS_AVAILABLE
                spread = long_return - short_return

            slices.append(
                ResearchFactorReturnSlice(
                    as_of=as_of,
                    total_observation_count=len(ordered),
                    eligible_observation_count=eligible_count,
                    long_bucket=1,
                    short_bucket=bucket_count,
                    long_return=long_return,
                    short_return=short_return,
                    long_short_return=spread,
                    status=status,
                    buckets=tuple(buckets),
                )
            )

        return ResearchFactorReturnSeries(
            factor_key=panel.factor_key,
            definition_version=panel.definition_version,
            horizon=panel.horizon,
            return_price_basis=panel.return_price_basis,
            bucket_count=bucket_count,
            weighting=self.WEIGHTING,
            long_bucket=1,
            short_bucket=bucket_count,
            construction=self.CONSTRUCTION,
            slices=tuple(slices),
        )

    @staticmethod
    def _assign_buckets(
        ordered_rows: list[ResearchFactorReturnRow],
        bucket_count: int,
    ) -> tuple[tuple[ResearchFactorReturnRow, int], ...]:
        count = len(ordered_rows)
        base_size, remainder = divmod(count, bucket_count)
        assignments: list[tuple[ResearchFactorReturnRow, int]] = []
        start = 0
        for bucket_number in range(1, bucket_count + 1):
            size = base_size + (1 if bucket_number <= remainder else 0)
            for row in ordered_rows[start : start + size]:
                assignments.append((row, bucket_number))
            start += size
        return tuple(assignments)

    @classmethod
    def _validate_inputs(
        cls,
        panel: ResearchFactorReturnPanel,
        bucket_count: int,
        minimum_observations_per_leg: int,
    ) -> None:
        if not isinstance(panel, ResearchFactorReturnPanel):
            raise InvalidInputError(
                "Factor return methodology requires a ResearchFactorReturnPanel."
            )
        if not panel.rows:
            raise InvalidInputError("Research factor return panel must not be empty.")
        if not isinstance(bucket_count, int) or isinstance(bucket_count, bool) or bucket_count < 2:
            raise InvalidInputError("bucket_count must be an integer greater than or equal to 2.")
        if not isinstance(minimum_observations_per_leg, int) or isinstance(
            minimum_observations_per_leg, bool
        ) or minimum_observations_per_leg < 1:
            raise InvalidInputError(
                "minimum_observations_per_leg must be a positive integer."
            )

        seen: set[tuple[int, datetime]] = set()
        for row in panel.rows:
            point = (row.security_id, row.factor_as_of)
            if point in seen:
                raise InvalidInputError(
                    "Research factor return panel must not contain duplicate security/as-of points."
                )
            seen.add(point)
            if not isinstance(row, ResearchFactorReturnRow):
                raise InvalidInputError(
                    "Research factor return rows must use the expected row contract."
                )
            if row.symbol.strip().upper() != row.factor_value.symbol.strip().upper():
                raise InvalidInputError(
                    "Factor return row symbol does not match its factor value."
                )
            if row.security_id != row.factor_value.security_id:
                raise InvalidInputError(
                    "Factor return row security_id does not match its factor value."
                )
            if row.factor_value.factor_key != panel.factor_key:
                raise InvalidInputError(
                    "Factor return row factor identity does not match the panel."
                )
            if row.factor_value.definition_version != panel.definition_version:
                raise InvalidInputError(
                    "Factor return row definition version does not match the panel."
                )
            if row.factor_value.as_of != row.factor_as_of:
                raise InvalidInputError(
                    "Factor return row factor value timestamp does not match factor_as_of."
                )
            if not isinstance(row.factor_rank, (int, float)) or not isfinite(float(row.factor_rank)):
                raise InvalidInputError("Factor return ranks must be finite.")
            if float(row.factor_rank) < 1.0:
                raise InvalidInputError("Factor return ranks must be positive.")
            if row.status == "AVAILABLE":
                if row.forward_return is None or not isfinite(float(row.forward_return)):
                    raise InvalidInputError(
                        "Available factor return rows require finite forward returns."
                    )
