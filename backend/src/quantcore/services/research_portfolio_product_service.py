from dataclasses import dataclass
from datetime import datetime

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
)
from quantcore.services.research_factor_panel_service import ResearchFactorPanelService
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionService,
)
from quantcore.services.research_signal_service import (
    ResearchSignalDefinition,
    ResearchSignalService,
)
from quantcore.services.research_strategy_service import (
    ResearchStrategyDefinition,
    ResearchStrategyService,
)


@dataclass(frozen=True)
class ResearchPortfolioProductResult:
    """Portfolio plus the deterministic research lineage needed by the API."""

    portfolio: ResearchPortfolio
    dataset_fingerprint: str
    dataset_identity: tuple[str, str] | None
    signal_construction: str


class ResearchPortfolioProductService:
    """Compose research signal and strategy contracts into a target portfolio.

    This is an API-facing orchestration boundary only. It delegates all
    analytical semantics to the existing deterministic research services and
    never creates holdings, orders, executions, or persisted portfolio state.
    """

    def __init__(
        self,
        historical_service: ResearchHistoricalAnalysisService,
        panel_service: ResearchFactorPanelService,
        cross_sectional_service: ResearchFactorCrossSectionalService,
        signal_service: ResearchSignalService,
        strategy_service: ResearchStrategyService,
        portfolio_service: ResearchPortfolioConstructionService,
    ) -> None:
        self._historical_service = historical_service
        self._panel_service = panel_service
        self._cross_sectional_service = cross_sectional_service
        self._signal_service = signal_service
        self._strategy_service = strategy_service
        self._portfolio_service = portfolio_service

    def construct(
        self,
        *,
        symbols: list[str] | tuple[str, ...],
        as_ofs: list[datetime] | tuple[datetime, ...],
        target_as_of: datetime,
        definition_identities: list[tuple[str, str]] | tuple[tuple[str, str], ...] | None,
        dataset_identity: tuple[str, str] | None,
        signal: ResearchSignalDefinition,
        factors: list[tuple[str, str, float, bool]]
        | tuple[tuple[str, str, float, bool], ...],
        strategy: ResearchStrategyDefinition,
    ) -> ResearchPortfolioProductResult:
        if not isinstance(target_as_of, datetime) or target_as_of.tzinfo is None:
            raise InvalidInputError("Portfolio target_as_of must be timezone-aware.")
        if any(not isinstance(value, datetime) or value.tzinfo is None for value in as_ofs):
            raise InvalidInputError("Portfolio signal as_ofs must be timezone-aware.")
        if target_as_of not in as_ofs:
            raise InvalidInputError("Portfolio target_as_of must be one of the requested signal as_ofs.")
        if len(factors) != len(signal.factor_identities):
            raise InvalidInputError(
                "Portfolio signal factors must match the signal definition factor identities."
            )

        validated_strategy = self._strategy_service.validate_definition(strategy)
        if validated_strategy.signal_identity != signal.identity:
            raise InvalidInputError(
                "Portfolio strategy signal identity must match the requested signal definition."
            )

        dataset = self._historical_service.build_historical_dataset(
            symbols,
            as_ofs=as_ofs,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
        )

        panels_by_factor = {}
        for factor_key, definition_version, _weight, higher_is_better in factors:
            identity = (factor_key.strip(), definition_version.strip())
            if identity not in signal.factor_identities:
                raise InvalidInputError(
                    "Portfolio signal factors must exactly match the signal definition identities."
                )
            panel = self._panel_service.build_factor_panel(
                dataset,
                factor_key=identity[0],
                definition_version=identity[1],
            )
            panels_by_factor[identity] = self._cross_sectional_service.rank_factor_panel(
                panel,
                higher_is_better=higher_is_better,
            )

        composite_signal = self._signal_service.construct_signal(signal, panels_by_factor)
        portfolio = self._portfolio_service.construct(
            validated_strategy,
            composite_signal,
            target_as_of,
        )
        return ResearchPortfolioProductResult(
            portfolio=portfolio,
            dataset_fingerprint=dataset.dataset_fingerprint,
            dataset_identity=dataset.dataset_identity,
            signal_construction=composite_signal.construction,
        )
