from dataclasses import dataclass
from datetime import datetime

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
    ResearchFactorRankedPanel,
)
from quantcore.services.research_factor_panel_service import ResearchFactorPanelService
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
)
from quantcore.services.research_portfolio_construction_service import (
    ResearchPortfolio,
    ResearchPortfolioConstructionService,
)
from quantcore.services.research_portfolio_factor_risk_service import (
    ResearchPortfolioFactorRiskService,
    ResearchPortfolioFactorRiskSnapshot,
)
from quantcore.services.research_portfolio_risk_service import (
    ResearchPortfolioRiskService,
    ResearchPortfolioRiskSnapshot,
)
from quantcore.services.research_portfolio_stress_service import (
    ResearchPortfolioStressResult,
    ResearchPortfolioStressService,
    ResearchStressScenarioDefinition,
)
from quantcore.services.research_rebalance_service import (
    ResearchRebalance,
    ResearchRebalanceDefinition,
    ResearchRebalanceService,
)
from quantcore.services.research_transaction_cost_service import (
    ResearchTransactionCostDefinition,
    ResearchTransactionCostResult,
    ResearchTransactionCostService,
)
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
    ResearchPortfolioConstraintResult,
    ResearchPortfolioConstraintService,
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


@dataclass(frozen=True)
class ResearchPortfolioRiskProductResult:
    """Portfolio plus its deterministic descriptive risk snapshot."""

    portfolio: ResearchPortfolioProductResult
    risk: ResearchPortfolioRiskSnapshot


@dataclass(frozen=True)
class ResearchPortfolioFactorRiskProductResult:
    """Portfolio plus deterministic rank-based factor exposures."""

    portfolio: ResearchPortfolioProductResult
    factor_risk: ResearchPortfolioFactorRiskSnapshot


@dataclass(frozen=True)
class ResearchPortfolioConstraintProductResult:
    """Portfolio plus deterministic constraint validation."""

    portfolio: ResearchPortfolioProductResult
    constraint: ResearchPortfolioConstraintResult


@dataclass(frozen=True)
class ResearchPortfolioStressProductResult:
    """Portfolio plus deterministic hypothetical stress analysis."""

    portfolio: ResearchPortfolioProductResult
    stress: ResearchPortfolioStressResult


@dataclass(frozen=True)
class ResearchPortfolioRebalanceProductResult:
    """Two deterministic portfolio states plus their weight transition."""

    current: ResearchPortfolioProductResult
    target: ResearchPortfolioProductResult
    rebalance: ResearchRebalance


@dataclass(frozen=True)
class ResearchPortfolioTransactionCostProductResult:
    """Two deterministic portfolio states, transition, and transaction cost."""

    current: ResearchPortfolioProductResult
    target: ResearchPortfolioProductResult
    rebalance: ResearchRebalance
    transaction_cost: ResearchTransactionCostResult


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
        risk_service: ResearchPortfolioRiskService | None = None,
        factor_risk_service: ResearchPortfolioFactorRiskService | None = None,
        constraint_service: ResearchPortfolioConstraintService | None = None,
        rebalance_service: ResearchRebalanceService | None = None,
        transaction_cost_service: ResearchTransactionCostService | None = None,
        stress_service: ResearchPortfolioStressService | None = None,
    ) -> None:
        self._historical_service = historical_service
        self._panel_service = panel_service
        self._cross_sectional_service = cross_sectional_service
        self._signal_service = signal_service
        self._strategy_service = strategy_service
        self._portfolio_service = portfolio_service
        self._risk_service = risk_service or ResearchPortfolioRiskService()
        self._factor_risk_service = factor_risk_service or ResearchPortfolioFactorRiskService()
        self._constraint_service = constraint_service or ResearchPortfolioConstraintService()
        self._rebalance_service = rebalance_service or ResearchRebalanceService()
        self._transaction_cost_service = transaction_cost_service or ResearchTransactionCostService()
        self._stress_service = stress_service or ResearchPortfolioStressService()

    def _construct_with_ranked_panels(
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
    ) -> tuple[ResearchPortfolioProductResult, dict[tuple[str, str], ResearchFactorRankedPanel]]:
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

        panels_by_factor: dict[tuple[str, str], ResearchFactorRankedPanel] = {}
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
        return (
            ResearchPortfolioProductResult(
                portfolio=portfolio,
                dataset_fingerprint=dataset.dataset_fingerprint,
                dataset_identity=dataset.dataset_identity,
                signal_construction=composite_signal.construction,
            ),
            panels_by_factor,
        )

    def construct_sequence(
        self,
        *,
        symbols: list[str] | tuple[str, ...],
        as_ofs: list[datetime] | tuple[datetime, ...],
        definition_identities: list[tuple[str, str]] | tuple[tuple[str, str], ...] | None,
        dataset_identity: tuple[str, str] | None,
        signal: ResearchSignalDefinition,
        factors: list[tuple[str, str, float, bool]]
        | tuple[tuple[str, str, float, bool], ...],
        strategy: ResearchStrategyDefinition,
    ) -> tuple[ResearchPortfolioProductResult, ...]:
        """Construct multiple target portfolios from one shared deterministic signal build."""
        if not as_ofs:
            raise InvalidInputError("Portfolio as_ofs must not be empty.")
        if any(not isinstance(value, datetime) or value.tzinfo is None for value in as_ofs):
            raise InvalidInputError("Portfolio signal as_ofs must be timezone-aware.")
        if tuple(as_ofs) != tuple(sorted(as_ofs)):
            raise InvalidInputError("Portfolio signal as_ofs must be supplied in ascending order.")
        if len(set(as_ofs)) != len(as_ofs):
            raise InvalidInputError("Portfolio signal as_ofs must not contain duplicates.")

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

        panels_by_factor: dict[tuple[str, str], ResearchFactorRankedPanel] = {}
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
        results: list[ResearchPortfolioProductResult] = []
        for target_as_of in as_ofs:
            portfolio = self._portfolio_service.construct(
                validated_strategy,
                composite_signal,
                target_as_of,
            )
            results.append(
                ResearchPortfolioProductResult(
                    portfolio=portfolio,
                    dataset_fingerprint=dataset.dataset_fingerprint,
                    dataset_identity=dataset.dataset_identity,
                    signal_construction=composite_signal.construction,
                )
            )
        return tuple(results)

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
        result, _panels_by_factor = self._construct_with_ranked_panels(
            symbols=symbols,
            as_ofs=as_ofs,
            target_as_of=target_as_of,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
        )
        return result

    def construct_with_risk(
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
    ) -> ResearchPortfolioRiskProductResult:
        portfolio_result = self.construct(
            symbols=symbols,
            as_ofs=as_ofs,
            target_as_of=target_as_of,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
        )
        risk = self._risk_service.snapshot(portfolio_result.portfolio)
        return ResearchPortfolioRiskProductResult(
            portfolio=portfolio_result,
            risk=risk,
        )

    def construct_with_constraints(
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
        constraint_definition: ResearchPortfolioConstraintDefinition,
    ) -> ResearchPortfolioConstraintProductResult:
        portfolio_result = self.construct(
            symbols=symbols,
            as_ofs=as_ofs,
            target_as_of=target_as_of,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
        )
        constraint = self._constraint_service.validate(
            portfolio_result.portfolio,
            constraint_definition,
        )
        return ResearchPortfolioConstraintProductResult(
            portfolio=portfolio_result,
            constraint=constraint,
        )

    def construct_with_factor_risk(
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
    ) -> ResearchPortfolioFactorRiskProductResult:
        portfolio_result, panels_by_factor = self._construct_with_ranked_panels(
            symbols=symbols,
            as_ofs=as_ofs,
            target_as_of=target_as_of,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
        )
        factor_risk = self._factor_risk_service.snapshot(
            portfolio_result.portfolio,
            panels_by_factor,
        )
        return ResearchPortfolioFactorRiskProductResult(
            portfolio=portfolio_result,
            factor_risk=factor_risk,
        )

    def construct_with_stress(
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
        scenario: ResearchStressScenarioDefinition,
        portfolio_value: float | None = None,
    ) -> ResearchPortfolioStressProductResult:
        """Construct one target portfolio and apply an explicit hypothetical stress scenario."""
        if not isinstance(scenario, ResearchStressScenarioDefinition):
            raise InvalidInputError(
                "Portfolio stress analysis requires a ResearchStressScenarioDefinition."
            )
        portfolio_result = self.construct(
            symbols=symbols,
            as_ofs=as_ofs,
            target_as_of=target_as_of,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
        )
        stress = self._stress_service.apply(
            portfolio_result.portfolio,
            scenario,
            portfolio_value=portfolio_value,
        )
        return ResearchPortfolioStressProductResult(
            portfolio=portfolio_result,
            stress=stress,
        )

    def construct_with_rebalance(
        self,
        *,
        symbols: list[str] | tuple[str, ...],
        as_ofs: list[datetime] | tuple[datetime, ...],
        current_as_of: datetime,
        target_as_of: datetime,
        definition_identities: list[tuple[str, str]] | tuple[tuple[str, str], ...] | None,
        dataset_identity: tuple[str, str] | None,
        signal: ResearchSignalDefinition,
        factors: list[tuple[str, str, float, bool]]
        | tuple[tuple[str, str, float, bool], ...],
        strategy: ResearchStrategyDefinition,
        rebalance_definition: ResearchRebalanceDefinition,
    ) -> ResearchPortfolioRebalanceProductResult:
        """Construct two deterministic portfolio states and calculate their transition."""
        if not isinstance(current_as_of, datetime) or current_as_of.tzinfo is None:
            raise InvalidInputError("Portfolio current_as_of must be timezone-aware.")
        if not isinstance(target_as_of, datetime) or target_as_of.tzinfo is None:
            raise InvalidInputError("Portfolio target_as_of must be timezone-aware.")
        if current_as_of >= target_as_of:
            raise InvalidInputError("Portfolio current_as_of must precede target_as_of.")
        if not isinstance(rebalance_definition, ResearchRebalanceDefinition):
            raise InvalidInputError("Portfolio rebalance requires a ResearchRebalanceDefinition.")

        current = self.construct(
            symbols=symbols,
            as_ofs=as_ofs,
            target_as_of=current_as_of,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
        )
        target = self.construct(
            symbols=symbols,
            as_ofs=as_ofs,
            target_as_of=target_as_of,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
        )

        rebalance = self._rebalance_service.rebalance(
            current.portfolio,
            target.portfolio,
            rebalance_definition,
            target_as_of,
        )
        return ResearchPortfolioRebalanceProductResult(
            current=current,
            target=target,
            rebalance=rebalance,
        )

    def construct_with_transaction_cost(
        self,
        *,
        symbols: list[str] | tuple[str, ...],
        as_ofs: list[datetime] | tuple[datetime, ...],
        current_as_of: datetime,
        target_as_of: datetime,
        definition_identities: list[tuple[str, str]] | tuple[tuple[str, str], ...] | None,
        dataset_identity: tuple[str, str] | None,
        signal: ResearchSignalDefinition,
        factors: list[tuple[str, str, float, bool]]
        | tuple[tuple[str, str, float, bool], ...],
        strategy: ResearchStrategyDefinition,
        rebalance_definition: ResearchRebalanceDefinition,
        transaction_cost_definition: ResearchTransactionCostDefinition,
    ) -> ResearchPortfolioTransactionCostProductResult:
        """Construct two portfolio states, calculate their transition, then cost it."""
        if not isinstance(transaction_cost_definition, ResearchTransactionCostDefinition):
            raise InvalidInputError(
                "Portfolio transaction cost analysis requires a ResearchTransactionCostDefinition."
            )
        result = self.construct_with_rebalance(
            symbols=symbols,
            as_ofs=as_ofs,
            current_as_of=current_as_of,
            target_as_of=target_as_of,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
            rebalance_definition=rebalance_definition,
        )
        transaction_cost = self._transaction_cost_service.calculate(
            result.rebalance,
            transaction_cost_definition,
        )
        return ResearchPortfolioTransactionCostProductResult(
            current=result.current,
            target=result.target,
            rebalance=result.rebalance,
            transaction_cost=transaction_cost,
        )
