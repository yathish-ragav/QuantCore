from dataclasses import dataclass
from datetime import datetime, timezone
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.price_service import PriceService
from quantcore.services.research_backtest_service import (
    ResearchBacktest,
    ResearchBacktestDefinition,
    ResearchBacktestService,
)
from quantcore.services.research_portfolio_constraint_service import (
    ResearchPortfolioConstraintDefinition,
)
from quantcore.services.research_portfolio_product_service import (
    ResearchPortfolioProductResult,
    ResearchPortfolioProductService,
)
from quantcore.services.research_rebalance_service import ResearchRebalanceDefinition
from quantcore.services.research_signal_service import ResearchSignalDefinition
from quantcore.services.research_strategy_service import ResearchStrategyDefinition
from quantcore.services.research_transaction_cost_service import (
    ResearchTransactionCostDefinition,
)


@dataclass(frozen=True)
class ResearchBacktestProductResult:
    """Deterministic backtest result with target-portfolio provenance."""

    backtest: ResearchBacktest
    target_portfolios: tuple[ResearchPortfolioProductResult, ...]


@dataclass(frozen=True)
class _ResearchBacktestPriceObservation:
    """Immutable adapter from persisted price revisions to the backtest protocol."""

    date: datetime
    close: float
    adjusted_close: float | None
    known_at: datetime
    revision_number: int


class ResearchBacktestProductService:
    """Compose portfolio construction and PIT price history into a backtest."""

    def __init__(
        self,
        portfolio_product_service: ResearchPortfolioProductService,
        price_service: PriceService,
        backtest_service: ResearchBacktestService | None = None,
    ) -> None:
        self._portfolio_product_service = portfolio_product_service
        self._price_service = price_service
        self._backtest_service = backtest_service or ResearchBacktestService()

    def run(
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
    ) -> ResearchBacktestProductResult:
        if not isinstance(backtest_definition, ResearchBacktestDefinition):
            raise InvalidInputError("Backtest product analysis requires a ResearchBacktestDefinition.")

        target_portfolios = self._portfolio_product_service.construct_sequence(
            symbols=symbols,
            as_ofs=as_ofs,
            definition_identities=definition_identities,
            dataset_identity=dataset_identity,
            signal=signal,
            factors=factors,
            strategy=strategy,
        )
        price_history_by_security = self._load_price_history(
            target_portfolios,
            backtest_definition.end_as_of,
        )
        backtest = self._backtest_service.run(
            backtest_definition,
            tuple(result.portfolio for result in target_portfolios),
            price_history_by_security,
            constraint_definition,
            rebalance_definition,
            transaction_cost_definition,
        )
        return ResearchBacktestProductResult(
            backtest=backtest,
            target_portfolios=target_portfolios,
        )

    def _load_price_history(
        self,
        target_portfolios: tuple[ResearchPortfolioProductResult, ...],
        known_as_of: datetime,
    ) -> dict[int, tuple[_ResearchBacktestPriceObservation, ...]]:
        symbol_by_security: dict[int, str] = {}
        for result in target_portfolios:
            for position in result.portfolio.positions:
                symbol = position.symbol.strip().upper()
                prior = symbol_by_security.get(position.security_id)
                if prior is not None and prior != symbol:
                    raise InvalidInputError(
                        f"Security {position.security_id} maps to conflicting symbols."
                    )
                symbol_by_security[position.security_id] = symbol

        histories: dict[int, tuple[_ResearchBacktestPriceObservation, ...]] = {}
        for security_id, symbol in sorted(symbol_by_security.items()):
            revisions = self._price_service.get_price_revision_history_known_as_of(
                symbol,
                known_as_of,
            )
            observations: list[_ResearchBacktestPriceObservation] = []
            for revision in revisions:
                date = revision.date
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                known_at = revision.known_at
                if known_at.tzinfo is None:
                    raise InvalidInputError(
                        "Persisted price revision known_at must be timezone-aware."
                    )
                observations.append(
                    _ResearchBacktestPriceObservation(
                        date=date,
                        close=revision.close,
                        adjusted_close=revision.adjusted_close,
                        known_at=known_at,
                        revision_number=revision.revision_number,
                    )
                )
            histories[security_id] = tuple(observations)
        return histories
