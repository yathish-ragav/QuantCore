from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_rebalance_service import ResearchRebalance, ResearchRebalanceStatus


@dataclass(frozen=True)
class ResearchTransactionCostDefinition:
    """Versioned proportional transaction-cost assumptions for a rebalance."""

    cost_key: str
    definition_version: str
    one_way_cost_bps: float
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.cost_key, str) or not self.cost_key.strip():
            raise InvalidInputError("Transaction cost key must be a non-empty string.")
        if not isinstance(self.definition_version, str) or not self.definition_version.strip():
            raise InvalidInputError("Transaction cost definition version must be a non-empty string.")
        if isinstance(self.one_way_cost_bps, bool):
            raise InvalidInputError("one_way_cost_bps must be a finite non-negative number.")
        try:
            cost_bps = float(self.one_way_cost_bps)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError("one_way_cost_bps must be numeric.") from exc
        if not isfinite(cost_bps):
            raise InvalidInputError("one_way_cost_bps must be finite.")
        if cost_bps < 0.0:
            raise InvalidInputError("one_way_cost_bps must be non-negative.")
        if self.description is not None and not isinstance(self.description, str):
            raise InvalidInputError("Transaction cost description must be a string or None.")

        object.__setattr__(self, "cost_key", self.cost_key.strip())
        object.__setattr__(self, "definition_version", self.definition_version.strip())
        object.__setattr__(self, "one_way_cost_bps", cost_bps)
        if self.description is not None:
            object.__setattr__(self, "description", self.description.strip() or None)

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable transaction-cost definition identity."""
        return self.cost_key, self.definition_version


class ResearchTransactionCostStatus(str, Enum):
    """Outcome of deterministic transaction-cost calculation."""

    CALCULATED = "CALCULATED"
    NO_TURNOVER = "NO_TURNOVER"


@dataclass(frozen=True)
class ResearchTransactionCostResult:
    """Immutable proportional transaction-cost result for one rebalance."""

    cost_key: str
    cost_definition_version: str
    rebalance_key: str
    rebalance_definition_version: str
    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    as_of: datetime
    turnover: float
    one_way_cost_bps: float
    cost_fraction: float
    cost_bps: float
    status: ResearchTransactionCostStatus


class ResearchTransactionCostService:
    """Calculate deterministic proportional transaction costs from rebalance turnover."""

    def calculate(
        self,
        rebalance: ResearchRebalance,
        definition: ResearchTransactionCostDefinition,
    ) -> ResearchTransactionCostResult:
        self._validate_inputs(rebalance, definition)

        turnover = float(rebalance.turnover)
        cost_bps = turnover * definition.one_way_cost_bps
        cost_fraction = cost_bps / 10_000.0
        if not isfinite(cost_bps) or not isfinite(cost_fraction):
            raise InvalidInputError("Transaction cost calculation must be finite.")

        status = (
            ResearchTransactionCostStatus.NO_TURNOVER
            if turnover == 0.0
            else ResearchTransactionCostStatus.CALCULATED
        )
        return ResearchTransactionCostResult(
            cost_key=definition.cost_key,
            cost_definition_version=definition.definition_version,
            rebalance_key=rebalance.rebalance_key,
            rebalance_definition_version=rebalance.rebalance_definition_version,
            strategy_key=rebalance.strategy_key,
            strategy_definition_version=rebalance.strategy_definition_version,
            signal_identity=rebalance.signal_identity,
            as_of=rebalance.as_of,
            turnover=turnover,
            one_way_cost_bps=definition.one_way_cost_bps,
            cost_fraction=cost_fraction,
            cost_bps=cost_bps,
            status=status,
        )

    @staticmethod
    def _validate_inputs(
        rebalance: ResearchRebalance,
        definition: ResearchTransactionCostDefinition,
    ) -> None:
        if not isinstance(rebalance, ResearchRebalance):
            raise InvalidInputError(
                "Transaction cost calculation requires a ResearchRebalance."
            )
        if not isinstance(definition, ResearchTransactionCostDefinition):
            raise InvalidInputError(
                "Transaction cost calculation requires a ResearchTransactionCostDefinition."
            )
        if not isinstance(rebalance.as_of, datetime) or rebalance.as_of.tzinfo is None:
            raise InvalidInputError("Transaction cost as_of must be timezone-aware.")
        if rebalance.status not in {
            ResearchRebalanceStatus.REBALANCED,
            ResearchRebalanceStatus.NO_CHANGES,
        }:
            raise InvalidInputError("Transaction cost calculation requires a valid rebalance status.")
        if isinstance(rebalance.turnover, bool):
            raise InvalidInputError("Rebalance turnover must be a finite non-negative number.")
        try:
            turnover = float(rebalance.turnover)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError("Rebalance turnover must be numeric.") from exc
        if not isfinite(turnover):
            raise InvalidInputError("Rebalance turnover must be finite.")
        if turnover < 0.0:
            raise InvalidInputError("Rebalance turnover must be non-negative.")
