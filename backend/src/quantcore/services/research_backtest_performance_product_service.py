from dataclasses import dataclass
from datetime import datetime

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_performance_service import (
    ResearchBacktestPerformance,
    ResearchBacktestPerformanceService,
)
from quantcore.services.research_backtest_product_service import (
    ResearchBacktestProductResult,
    ResearchBacktestProductService,
)
from quantcore.services.research_backtest_service import ResearchBacktestDefinition
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
)
from quantcore.services.research_rebalance_service import ResearchRebalanceDefinition
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition
from quantcore.services.research_transaction_cost_service import (
    ResearchTransactionCostDefinition,
)


@dataclass(frozen=True)
class ResearchBacktestPerformanceProductResult:
    """Backtest performance plus the deterministic backtest provenance."""

    backtest: ResearchBacktestProductResult
    performance: ResearchBacktestPerformance


class ResearchBacktestPerformanceProductService:
    """Compose the deterministic backtest and performance analysis services."""

    def __init__(
        self,
        backtest_product_service: ResearchBacktestProductService,
        performance_service: ResearchBacktestPerformanceService | None = None,
    ) -> None:
        self._backtest_product_service = backtest_product_service
        self._performance_service = performance_service or ResearchBacktestPerformanceService()

    def analyze(
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
        backtest_definition: ResearchBacktestDefinition,
        constraint_definition: ResearchPortfolioConstraintDefinition,
        rebalance_definition: ResearchRebalanceDefinition,
        transaction_cost_definition: ResearchTransactionCostDefinition,
    ) -> ResearchBacktestPerformanceProductResult:
        if not isinstance(backtest_definition, ResearchBacktestDefinition):
            raise InvalidInputError(
                "Backtest performance analysis requires a ResearchBacktestDefinition."
            )

        backtest = self._backtest_product_service.run(
            symbols=symbols,
            as_ofs=as_ofs,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
            backtest_definition=backtest_definition,
            constraint_definition=constraint_definition,
            rebalance_definition=rebalance_definition,
            transaction_cost_definition=transaction_cost_definition,
        )
        performance = self._performance_service.analyze(backtest.backtest)
        return ResearchBacktestPerformanceProductResult(
            backtest=backtest,
            performance=performance,
        )
