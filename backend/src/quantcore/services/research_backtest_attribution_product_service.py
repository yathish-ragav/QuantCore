from dataclasses import dataclass
from datetime import datetime

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_backtest_attribution_service import (
    ResearchBacktestAttribution,
    ResearchBacktestAttributionService,
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
class ResearchBacktestAttributionProductResult:
    """Backtest attribution with the exact backtest valuation inputs."""

    backtest: ResearchBacktestProductResult
    attribution: ResearchBacktestAttribution


class ResearchBacktestAttributionProductService:
    """Compose the deterministic backtest and attribution services."""

    def __init__(
        self,
        backtest_product_service: ResearchBacktestProductService,
        attribution_service: ResearchBacktestAttributionService | None = None,
    ) -> None:
        self._backtest_product_service = backtest_product_service
        self._attribution_service = attribution_service or ResearchBacktestAttributionService()

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
    ) -> ResearchBacktestAttributionProductResult:
        if not isinstance(backtest_definition, ResearchBacktestDefinition):
            raise InvalidInputError(
                "Backtest attribution analysis requires a ResearchBacktestDefinition."
            )

        backtest_result = self._backtest_product_service.run(
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
        price_history = backtest_result.price_history_by_security
        if price_history is None:
            raise InvalidInputError(
                "Backtest attribution requires the valuation price history produced by the backtest."
            )

        attribution = self._attribution_service.attribute(
            backtest_result.backtest,
            tuple(result.portfolio for result in backtest_result.target_portfolios),
            price_history,
        )
        return ResearchBacktestAttributionProductResult(
            backtest=backtest_result,
            attribution=attribution,
        )
