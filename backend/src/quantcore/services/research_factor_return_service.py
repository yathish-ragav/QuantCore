from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable, Mapping, Protocol

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)


class ResearchPriceObservation(Protocol):
    """Minimum price-observation contract required for forward-return labels."""

    date: datetime
    close: float
    adjusted_close: float | None


@dataclass(frozen=True)
class ResearchFactorReturnRow:
    """One factor observation aligned with a realized forward return outcome."""

    symbol: str
    security_id: int
    factor_as_of: datetime
    factor_value: ResearchFactorValue
    factor_rank: float
    normalized_rank: float
    horizon: int
    entry_date: datetime | None
    exit_date: datetime | None
    entry_price: float | None
    exit_price: float | None
    forward_return: float | None
    return_price_basis: PriceBasis
    status: str


@dataclass(frozen=True)
class ResearchFactorReturnPanel:
    """Immutable forward-return outcomes aligned to one ranked factor panel."""

    factor_key: str
    definition_version: str
    horizon: int
    return_price_basis: PriceBasis
    entry_policy: str
    rows: tuple[ResearchFactorReturnRow, ...]


class ResearchFactorReturnService:
    """Align ranked factor observations with deterministic future return outcomes."""

    ENTRY_POLICY = "NEXT_AVAILABLE_PRICE_AFTER_FACTOR_AS_OF"
    STATUS_AVAILABLE = "AVAILABLE"
    STATUS_HORIZON_UNAVAILABLE = "HORIZON_UNAVAILABLE"

    def compute_forward_returns(
        self,
        panel: ResearchFactorRankedPanel,
        price_history_by_security: Mapping[int, Iterable[ResearchPriceObservation]],
        *,
        horizon: int,
        return_price_basis: PriceBasis = PriceBasis.ADJUSTED,
    ) -> ResearchFactorReturnPanel:
        """Attach a realized forward return to each factor observation.

        The factor observation at ``factor_as_of`` is never allowed to consume a
        price dated at or before that timestamp. The entry price is therefore the
        first available price observation strictly after ``factor_as_of``. The
        exit price is ``horizon`` trading observations after that entry point.

        Future prices are outcome labels, not factor inputs: using them here does
        not leak future information into the factor observation itself. If the
        requested horizon is unavailable, the row is retained with an explicit
        ``HORIZON_UNAVAILABLE`` status rather than silently dropped.
        """
        self._validate_inputs(panel, price_history_by_security, horizon, return_price_basis)

        rows: list[ResearchFactorReturnRow] = []
        for factor_row in panel.rows:
            prices = self._normalize_price_history(
                price_history_by_security.get(factor_row.security_id, ()),
                factor_row.security_id,
            )
            entry_index = self._find_entry_index(prices, factor_row.as_of)

            if entry_index is None or entry_index + horizon >= len(prices):
                rows.append(
                    ResearchFactorReturnRow(
                        symbol=factor_row.symbol.strip().upper(),
                        security_id=factor_row.security_id,
                        factor_as_of=factor_row.as_of,
                        factor_value=factor_row.factor_value,
                        factor_rank=factor_row.rank,
                        normalized_rank=factor_row.normalized_rank,
                        horizon=horizon,
                        entry_date=None,
                        exit_date=None,
                        entry_price=None,
                        exit_price=None,
                        forward_return=None,
                        return_price_basis=return_price_basis,
                        status=self.STATUS_HORIZON_UNAVAILABLE,
                    )
                )
                continue

            entry, entry_date = prices[entry_index]
            exit_observation, exit_date = prices[entry_index + horizon]
            entry_price = self._select_price(entry, return_price_basis)
            exit_price = self._select_price(exit_observation, return_price_basis)
            if entry_price <= 0.0 or exit_price <= 0.0:
                raise InvalidInputError(
                    "Forward-return prices must be strictly positive."
                )

            forward_return = exit_price / entry_price - 1.0
            if not isfinite(forward_return):
                raise InvalidInputError("Forward return must be finite.")

            rows.append(
                ResearchFactorReturnRow(
                    symbol=factor_row.symbol.strip().upper(),
                    security_id=factor_row.security_id,
                    factor_as_of=factor_row.as_of,
                    factor_value=factor_row.factor_value,
                    factor_rank=factor_row.rank,
                    normalized_rank=factor_row.normalized_rank,
                    horizon=horizon,
                    entry_date=entry_date,
                    exit_date=exit_date,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    forward_return=forward_return,
                    return_price_basis=return_price_basis,
                    status=self.STATUS_AVAILABLE,
                )
            )

        return ResearchFactorReturnPanel(
            factor_key=panel.factor_key,
            definition_version=panel.definition_version,
            horizon=horizon,
            return_price_basis=return_price_basis,
            entry_policy=self.ENTRY_POLICY,
            rows=tuple(rows),
        )

    @classmethod
    def _validate_inputs(
        cls,
        panel: ResearchFactorRankedPanel,
        price_history_by_security: Mapping[int, Iterable[ResearchPriceObservation]],
        horizon: int,
        return_price_basis: PriceBasis,
    ) -> None:
        if not isinstance(panel, ResearchFactorRankedPanel):
            raise InvalidInputError(
                "Factor returns require a ResearchFactorRankedPanel."
            )
        if not panel.rows:
            raise InvalidInputError("Research factor ranked panel must not be empty.")
        if not isinstance(price_history_by_security, Mapping):
            raise InvalidInputError("Price history must be keyed by security ID.")
        if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
            raise InvalidInputError("Forward-return horizon must be a positive integer.")
        if not isinstance(return_price_basis, PriceBasis):
            raise InvalidInputError("Return price basis must be a valid PriceBasis.")

        now = datetime.now(timezone.utc)
        seen: set[tuple[int, datetime]] = set()
        for row in panel.rows:
            if not isinstance(row, ResearchFactorRankRow):
                raise InvalidInputError(
                    "Research factor return rows must use the expected ranked-row contract."
                )
            if not isinstance(row.as_of, datetime) or row.as_of.tzinfo is None:
                raise InvalidInputError("Factor as_of must be timezone-aware.")
            if row.as_of > now:
                raise InvalidInputError("Factor as_of must not be in the future.")
            if not isinstance(row.security_id, int):
                raise InvalidInputError("Factor security_id must be an integer.")
            point = (row.security_id, row.as_of)
            if point in seen:
                raise InvalidInputError(
                    "Research factor ranked panel must not contain duplicate security/as-of points."
                )
            seen.add(point)

    @classmethod
    def _normalize_price_history(
        cls,
        observations: Iterable[ResearchPriceObservation],
        security_id: int,
    ) -> tuple[tuple[ResearchPriceObservation, datetime], ...]:
        try:
            values = tuple(observations)
        except TypeError as exc:
            raise InvalidInputError(
                f"Price history for security {security_id} must be iterable."
            ) from exc
        if not values:
            return ()

        normalized: list[tuple[ResearchPriceObservation, datetime]] = []
        seen_dates: set[datetime] = set()
        for observation in values:
            date = getattr(observation, "date", None)
            if not isinstance(date, datetime) or date.tzinfo is None:
                raise InvalidInputError(
                    "Price observation date must be a timezone-aware datetime."
                )

            if date in seen_dates:
                raise InvalidInputError(
                    f"Price history for security {security_id} contains duplicate dates."
                )
            seen_dates.add(date)

            close = getattr(observation, "close", None)
            adjusted_close = getattr(observation, "adjusted_close", None)
            cls._validate_price_value(close, "close")
            if adjusted_close is not None:
                cls._validate_price_value(adjusted_close, "adjusted_close")
            normalized.append((observation, date))

        normalized.sort(key=lambda item: item[1])
        return tuple(normalized)

    @staticmethod
    def _validate_price_value(value: object, field: str) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError(f"Price observation {field} must be numeric.") from exc
        if not isfinite(numeric):
            raise InvalidInputError(f"Price observation {field} must be finite.")

    @staticmethod
    def _find_entry_index(
        prices: tuple[tuple[ResearchPriceObservation, datetime], ...],
        factor_as_of: datetime,
    ) -> int | None:
        for index, (_, price_date) in enumerate(prices):
            if price_date > factor_as_of:
                return index
        return None

    @staticmethod
    def _select_price(
        observation: ResearchPriceObservation,
        return_price_basis: PriceBasis,
    ) -> float:
        if return_price_basis is PriceBasis.UNADJUSTED:
            value = float(observation.close)
        else:
            adjusted_close = getattr(observation, "adjusted_close", None)
            if adjusted_close is None:
                raise InvalidInputError(
                    "Adjusted forward returns require adjusted_close on every selected price observation."
                )
            value = float(adjusted_close)
        if not isfinite(value):
            raise InvalidInputError("Selected return price must be finite.")
        return value
