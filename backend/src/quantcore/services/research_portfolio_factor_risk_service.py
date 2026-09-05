from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Mapping

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)
from quantcore.services.research_portfolio_construction_service import ResearchPortfolio


ResearchFactorIdentity = tuple[str, str]


@dataclass(frozen=True)
class ResearchPortfolioFactorExposure:
    """Rank-based factor exposure for one portfolio/factor identity.

    Exposure is the signed portfolio-weighted sum of centered normalized factor
    ranks. It is therefore descriptive and comparable across portfolios after
    dividing by gross portfolio exposure. This is not a beta or covariance
    estimate.
    """

    factor_identity: ResearchFactorIdentity
    as_of: datetime
    position_count: int
    factor_observation_count: int
    exposure: float
    long_exposure: float
    short_exposure: float
    gross_factor_exposure: float
    gross_normalized_exposure: float


@dataclass(frozen=True)
class ResearchPortfolioFactorRiskSnapshot:
    """Immutable rank-based factor-risk snapshot for a target portfolio."""

    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    position_count: int
    factor_exposures: tuple[ResearchPortfolioFactorExposure, ...]


class ResearchPortfolioFactorRiskService:
    """Compute deterministic rank-based factor exposures for a target portfolio.

    The service consumes an existing constructed portfolio and versioned,
    rank-normalized factor panels. It uses only factor observations at the
    portfolio's exact ``as_of`` boundary and never fetches data, estimates
    covariance, forecasts returns, or changes portfolio weights.
    """

    def snapshot(
        self,
        portfolio: ResearchPortfolio,
        panels_by_factor: Mapping[ResearchFactorIdentity, ResearchFactorRankedPanel],
    ) -> ResearchPortfolioFactorRiskSnapshot:
        self._validate_inputs(portfolio, panels_by_factor)

        factors: list[ResearchPortfolioFactorExposure] = []
        for identity in sorted(panels_by_factor):
            panel = panels_by_factor[identity]
            indexed = {
                (row.security_id, row.as_of): row
                for row in panel.rows
            }
            selected_rows: list[tuple[object, ResearchFactorRankRow]] = []
            for position in portfolio.positions:
                key = (position.security_id, portfolio.as_of)
                row = indexed.get(key)
                if row is None:
                    raise InvalidInputError(
                        f"Missing factor observation for security {position.security_id} "
                        f"and factor {identity} at {portfolio.as_of.isoformat()}."
                    )
                selected_rows.append((position, row))

            weighted_exposure = 0.0
            long_exposure = 0.0
            short_exposure = 0.0
            gross_factor_exposure = 0.0

            for position, row in selected_rows:
                centered_rank = 2.0 * float(row.normalized_rank) - 1.0
                contribution = float(position.target_weight) * centered_rank
                if not isfinite(contribution):
                    raise InvalidInputError("Portfolio factor exposure must be finite.")

                weighted_exposure += contribution
                if position.target_weight > 0.0:
                    long_exposure += contribution
                elif position.target_weight < 0.0:
                    short_exposure += contribution
                gross_factor_exposure += abs(contribution)

            gross_exposure = float(portfolio.gross_exposure)
            gross_normalized = (
                weighted_exposure / gross_exposure
                if gross_exposure > 0.0
                else 0.0
            )

            values = (
                weighted_exposure,
                long_exposure,
                short_exposure,
                gross_factor_exposure,
                gross_normalized,
            )
            if not all(isfinite(value) for value in values):
                raise InvalidInputError("Portfolio factor exposure metrics must be finite.")

            factors.append(
                ResearchPortfolioFactorExposure(
                    factor_identity=identity,
                    as_of=portfolio.as_of,
                    position_count=len(portfolio.positions),
                    factor_observation_count=len(selected_rows),
                    exposure=weighted_exposure,
                    long_exposure=long_exposure,
                    short_exposure=short_exposure,
                    gross_factor_exposure=gross_factor_exposure,
                    gross_normalized_exposure=gross_normalized,
                )
            )

        return ResearchPortfolioFactorRiskSnapshot(
            strategy_key=portfolio.strategy_key,
            strategy_definition_version=portfolio.strategy_definition_version,
            signal_identity=portfolio.signal_identity,
            as_of=portfolio.as_of,
            position_count=len(portfolio.positions),
            factor_exposures=tuple(factors),
        )

    @staticmethod
    def _validate_inputs(
        portfolio: ResearchPortfolio,
        panels_by_factor: Mapping[ResearchFactorIdentity, ResearchFactorRankedPanel],
    ) -> None:
        if not isinstance(portfolio, ResearchPortfolio):
            raise InvalidInputError(
                "Portfolio factor risk requires a ResearchPortfolio."
            )
        if portfolio.status.name != "CONSTRUCTED":
            raise InvalidInputError(
                "Portfolio factor risk requires a constructed target portfolio."
            )
        if not isinstance(portfolio.as_of, datetime) or portfolio.as_of.tzinfo is None:
            raise InvalidInputError("Portfolio factor risk as_of must be timezone-aware.")
        if not isinstance(panels_by_factor, Mapping) or not panels_by_factor:
            raise InvalidInputError(
                "Portfolio factor risk requires at least one factor panel."
            )

        seen_positions: set[int] = set()
        for position in portfolio.positions:
            if position.security_id in seen_positions:
                raise InvalidInputError(
                    "Portfolio factor risk requires unique portfolio security IDs."
                )
            seen_positions.add(position.security_id)
            if position.as_of != portfolio.as_of:
                raise InvalidInputError(
                    "Portfolio position as_of must match the portfolio as_of."
                )
            if not isfinite(float(position.target_weight)):
                raise InvalidInputError("Portfolio position weights must be finite.")

        for identity, panel in panels_by_factor.items():
            if (
                not isinstance(identity, tuple)
                or len(identity) != 2
                or not all(isinstance(value, str) and value.strip() for value in identity)
            ):
                raise InvalidInputError(
                    "Portfolio factor identities must be (factor_key, definition_version) tuples."
                )
            if not isinstance(panel, ResearchFactorRankedPanel):
                raise InvalidInputError(
                    "Portfolio factor risk inputs must be ResearchFactorRankedPanel values."
                )
            if (panel.factor_key, panel.definition_version) != (
                identity[0].strip(),
                identity[1].strip(),
            ):
                raise InvalidInputError(
                    "Portfolio factor panel identity does not match its mapping key."
                )
            if not panel.rows:
                raise InvalidInputError("Portfolio factor panels must not be empty.")

            seen_points: set[tuple[int, datetime]] = set()
            for row in panel.rows:
                if not isinstance(row, ResearchFactorRankRow):
                    raise InvalidInputError(
                        "Portfolio factor panels must contain ResearchFactorRankRow values."
                    )
                if not isinstance(row.as_of, datetime) or row.as_of.tzinfo is None:
                    raise InvalidInputError(
                        "Portfolio factor row as_of must be timezone-aware."
                    )
                if not isinstance(row.security_id, int) or isinstance(row.security_id, bool):
                    raise InvalidInputError(
                        "Portfolio factor row security_id must be an integer."
                    )
                point = (row.security_id, row.as_of)
                if point in seen_points:
                    raise InvalidInputError(
                        "Portfolio factor panels must not contain duplicate security/as-of points."
                    )
                seen_points.add(point)
                if not isinstance(row.factor_value, ResearchFactorValue):
                    raise InvalidInputError(
                        "Portfolio factor rows must contain ResearchFactorValue values."
                    )
                if (row.factor_value.factor_key, row.factor_value.definition_version) != (
                    identity[0].strip(),
                    identity[1].strip(),
                ):
                    raise InvalidInputError(
                        "Portfolio factor row identity does not match its panel identity."
                    )
                if row.factor_value.security_id != row.security_id:
                    raise InvalidInputError(
                        "Portfolio factor row security_id must match its factor value."
                    )
                if row.factor_value.as_of != row.as_of:
                    raise InvalidInputError(
                        "Portfolio factor row as_of must match its factor value."
                    )
                if row.factor_value.symbol.strip().upper() != row.symbol.strip().upper():
                    raise InvalidInputError(
                        "Portfolio factor row symbol must match its factor value."
                    )
                normalized_rank = float(row.normalized_rank)
                if not isfinite(normalized_rank) or not 0.0 <= normalized_rank <= 1.0:
                    raise InvalidInputError(
                        "Portfolio factor normalized ranks must be finite and within [0, 1]."
                    )
