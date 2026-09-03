from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_signal_service import ResearchSignalPanel, ResearchSignalRow
from quantcore.services.research_strategy_service import (
    ResearchStrategyDefinition,
    ResearchStrategyDirection,
)


class ResearchPortfolioPositionSide(str, Enum):
    """Directional side of a target research portfolio position."""

    LONG = "LONG"
    SHORT = "SHORT"


class ResearchPortfolioConstructionStatus(str, Enum):
    """Outcome of deterministic portfolio construction for one as-of point."""

    CONSTRUCTED = "CONSTRUCTED"
    NO_ELIGIBLE_SECURITIES = "NO_ELIGIBLE_SECURITIES"
    INCOMPLETE_LONG_SHORT = "INCOMPLETE_LONG_SHORT"


@dataclass(frozen=True)
class ResearchPortfolioPosition:
    """One target holding produced by deterministic portfolio construction."""

    symbol: str
    security_id: int
    as_of: datetime
    signal_score: float
    side: ResearchPortfolioPositionSide
    target_weight: float


@dataclass(frozen=True)
class ResearchPortfolio:
    """Immutable target portfolio for one strategy at one information boundary.

    Weights are intentionally target weights rather than orders or executions.
    Long-only and short-only strategies are equal-weighted across eligible
    securities. Long-short strategies are equal-weighted within each leg with
    equal dollar magnitude on the long and short sides, producing zero net
    exposure when both legs are populated.
    """

    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    status: ResearchPortfolioConstructionStatus
    positions: tuple[ResearchPortfolioPosition, ...]
    eligible_count: int
    long_count: int
    short_count: int
    gross_exposure: float
    net_exposure: float
    construction: str


class ResearchPortfolioConstructionService:
    """Construct deterministic target weights from a validated strategy signal."""

    CONSTRUCTION_LONG_ONLY = "EQUAL_WEIGHT_LONG_ONLY"
    CONSTRUCTION_SHORT_ONLY = "EQUAL_WEIGHT_SHORT_ONLY"
    CONSTRUCTION_LONG_SHORT = "EQUAL_WEIGHT_DOLLAR_NEUTRAL_LONG_SHORT"

    def construct(
        self,
        strategy: ResearchStrategyDefinition,
        signal_panel: ResearchSignalPanel,
        as_of: datetime,
    ) -> ResearchPortfolio:
        self._validate_inputs(strategy, signal_panel, as_of)

        rows = tuple(row for row in signal_panel.rows if row.as_of == as_of)
        eligible_long: list[ResearchSignalRow] = []
        eligible_short: list[ResearchSignalRow] = []

        for row in rows:
            score = float(row.score)
            if strategy.direction is ResearchStrategyDirection.LONG_ONLY:
                if score >= strategy.long_threshold:  # type: ignore[operator]
                    eligible_long.append(row)
            elif strategy.direction is ResearchStrategyDirection.SHORT_ONLY:
                if score <= strategy.short_threshold:  # type: ignore[operator]
                    eligible_short.append(row)
            else:
                if score >= strategy.long_threshold:  # type: ignore[operator]
                    eligible_long.append(row)
                elif score <= strategy.short_threshold:  # type: ignore[operator]
                    eligible_short.append(row)

        eligible_long.sort(key=lambda row: (row.security_id, row.symbol))
        eligible_short.sort(key=lambda row: (row.security_id, row.symbol))

        if strategy.direction is ResearchStrategyDirection.LONG_SHORT:
            if not eligible_long and not eligible_short:
                return self._empty_result(
                    strategy,
                    as_of,
                    ResearchPortfolioConstructionStatus.NO_ELIGIBLE_SECURITIES,
                )
            if not eligible_long or not eligible_short:
                return self._empty_result(
                    strategy,
                    as_of,
                    ResearchPortfolioConstructionStatus.INCOMPLETE_LONG_SHORT,
                    eligible_count=len(eligible_long) + len(eligible_short),
                    long_count=len(eligible_long),
                    short_count=len(eligible_short),
                )

            long_weight = 1.0 / len(eligible_long)
            short_weight = -1.0 / len(eligible_short)
            positions = tuple(
                self._position(row, ResearchPortfolioPositionSide.LONG, long_weight)
                for row in eligible_long
            ) + tuple(
                self._position(row, ResearchPortfolioPositionSide.SHORT, short_weight)
                for row in eligible_short
            )
            return self._result(
                strategy,
                as_of,
                ResearchPortfolioConstructionStatus.CONSTRUCTED,
                positions,
                len(eligible_long) + len(eligible_short),
                len(eligible_long),
                len(eligible_short),
                self.CONSTRUCTION_LONG_SHORT,
            )

        if strategy.direction is ResearchStrategyDirection.LONG_ONLY:
            if not eligible_long:
                return self._empty_result(
                    strategy,
                    as_of,
                    ResearchPortfolioConstructionStatus.NO_ELIGIBLE_SECURITIES,
                )
            weight = 1.0 / len(eligible_long)
            positions = tuple(
                self._position(row, ResearchPortfolioPositionSide.LONG, weight)
                for row in eligible_long
            )
            return self._result(
                strategy,
                as_of,
                ResearchPortfolioConstructionStatus.CONSTRUCTED,
                positions,
                len(eligible_long),
                len(eligible_long),
                0,
                self.CONSTRUCTION_LONG_ONLY,
            )

        if not eligible_short:
            return self._empty_result(
                strategy,
                as_of,
                ResearchPortfolioConstructionStatus.NO_ELIGIBLE_SECURITIES,
            )
        weight = -1.0 / len(eligible_short)
        positions = tuple(
            self._position(row, ResearchPortfolioPositionSide.SHORT, weight)
            for row in eligible_short
        )
        return self._result(
            strategy,
            as_of,
            ResearchPortfolioConstructionStatus.CONSTRUCTED,
            positions,
            len(eligible_short),
            0,
            len(eligible_short),
            self.CONSTRUCTION_SHORT_ONLY,
        )

    @staticmethod
    def _position(
        row: ResearchSignalRow,
        side: ResearchPortfolioPositionSide,
        target_weight: float,
    ) -> ResearchPortfolioPosition:
        return ResearchPortfolioPosition(
            symbol=row.symbol.strip().upper(),
            security_id=row.security_id,
            as_of=row.as_of,
            signal_score=float(row.score),
            side=side,
            target_weight=target_weight,
        )

    @classmethod
    def _result(
        cls,
        strategy: ResearchStrategyDefinition,
        as_of: datetime,
        status: ResearchPortfolioConstructionStatus,
        positions: tuple[ResearchPortfolioPosition, ...],
        eligible_count: int,
        long_count: int,
        short_count: int,
        construction: str,
    ) -> ResearchPortfolio:
        gross_exposure = sum(abs(position.target_weight) for position in positions)
        net_exposure = sum(position.target_weight for position in positions)
        if not isfinite(gross_exposure) or not isfinite(net_exposure):
            raise InvalidInputError("Portfolio exposures must be finite.")
        return ResearchPortfolio(
            strategy_key=strategy.strategy_key,
            strategy_definition_version=strategy.definition_version,
            signal_identity=strategy.signal_identity,
            as_of=as_of,
            status=status,
            positions=positions,
            eligible_count=eligible_count,
            long_count=long_count,
            short_count=short_count,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            construction=construction,
        )

    @classmethod
    def _empty_result(
        cls,
        strategy: ResearchStrategyDefinition,
        as_of: datetime,
        status: ResearchPortfolioConstructionStatus,
        eligible_count: int = 0,
        long_count: int = 0,
        short_count: int = 0,
    ) -> ResearchPortfolio:
        return cls._result(
            strategy,
            as_of,
            status,
            (),
            eligible_count,
            long_count,
            short_count,
            "NO_TARGET_POSITIONS",
        )

    @staticmethod
    def _validate_inputs(
        strategy: ResearchStrategyDefinition,
        signal_panel: ResearchSignalPanel,
        as_of: datetime,
    ) -> None:
        if not isinstance(strategy, ResearchStrategyDefinition):
            raise InvalidInputError(
                "Portfolio construction requires a ResearchStrategyDefinition."
            )
        if not isinstance(signal_panel, ResearchSignalPanel):
            raise InvalidInputError("Portfolio construction requires a ResearchSignalPanel.")
        if not isinstance(as_of, datetime) or as_of.tzinfo is None:
            raise InvalidInputError("Portfolio construction as_of must be timezone-aware.")
        if signal_panel.signal_key.strip() != strategy.signal_identity[0] or signal_panel.definition_version.strip() != strategy.signal_identity[1]:
            raise InvalidInputError(
                "Portfolio construction signal identity does not match the strategy definition."
            )
        if not signal_panel.rows:
            raise InvalidInputError("Portfolio construction signal panel must not be empty.")

        seen: set[tuple[int, datetime]] = set()
        for row in signal_panel.rows:
            if not isinstance(row, ResearchSignalRow):
                raise InvalidInputError(
                    "Portfolio construction signal rows must use the expected row contract."
                )
            if not isinstance(row.as_of, datetime) or row.as_of.tzinfo is None:
                raise InvalidInputError("Portfolio signal row as_of must be timezone-aware.")
            if not isinstance(row.security_id, int) or isinstance(row.security_id, bool):
                raise InvalidInputError("Portfolio signal security_id must be an integer.")
            if not isinstance(row.symbol, str) or not row.symbol.strip():
                raise InvalidInputError("Portfolio signal symbol must be a non-empty string.")
            try:
                score = float(row.score)
            except (TypeError, ValueError) as exc:
                raise InvalidInputError("Portfolio signal scores must be numeric.") from exc
            if not isfinite(score) or not 0.0 <= score <= 1.0:
                raise InvalidInputError("Portfolio signal scores must be finite and within [0, 1].")
            if not isinstance(row.centered_score, (int, float)) or not isfinite(float(row.centered_score)):
                raise InvalidInputError("Portfolio signal centered scores must be finite.")
            point = (row.security_id, row.as_of)
            if point in seen:
                raise InvalidInputError(
                    "Portfolio construction signal panel must not contain duplicate security/as-of points."
                )
            seen.add(point)
