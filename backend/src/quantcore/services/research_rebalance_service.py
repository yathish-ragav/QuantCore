from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_portfolio_construction_service import ResearchPortfolio


class ResearchRebalanceFrequency(str, Enum):
    """Declared cadence for evaluating a research portfolio rebalance."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class ResearchRebalanceActionType(str, Enum):
    """Deterministic weight transition classification for one security."""

    ADD = "ADD"
    INCREASE = "INCREASE"
    REDUCE = "REDUCE"
    REMOVE = "REMOVE"
    REVERSE = "REVERSE"


class ResearchRebalanceStatus(str, Enum):
    """Outcome of deterministic rebalance calculation."""

    REBALANCED = "REBALANCED"
    NO_CHANGES = "NO_CHANGES"


@dataclass(frozen=True)
class ResearchRebalanceDefinition:
    """Versioned declaration of when a strategy may be re-evaluated."""

    rebalance_key: str
    definition_version: str
    frequency: ResearchRebalanceFrequency
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rebalance_key, str) or not self.rebalance_key.strip():
            raise InvalidInputError("Rebalance key must be a non-empty string.")
        if not isinstance(self.definition_version, str) or not self.definition_version.strip():
            raise InvalidInputError("Rebalance definition version must be a non-empty string.")
        if not isinstance(self.frequency, ResearchRebalanceFrequency):
            raise InvalidInputError("Rebalance frequency must be a ResearchRebalanceFrequency.")
        if self.description is not None and not isinstance(self.description, str):
            raise InvalidInputError("Rebalance description must be a string or None.")
        object.__setattr__(self, "rebalance_key", self.rebalance_key.strip())
        object.__setattr__(self, "definition_version", self.definition_version.strip())
        if self.description is not None:
            object.__setattr__(self, "description", self.description.strip() or None)

    @property
    def identity(self) -> tuple[str, str]:
        """Return the stable rebalance definition identity."""
        return self.rebalance_key, self.definition_version


@dataclass(frozen=True)
class ResearchRebalanceAction:
    """One non-zero target-weight transition between two portfolio states."""

    symbol: str
    security_id: int
    current_weight: float
    target_weight: float
    weight_delta: float
    action: ResearchRebalanceActionType


@dataclass(frozen=True)
class ResearchRebalance:
    """Immutable deterministic transition from current to target portfolio."""

    rebalance_key: str
    rebalance_definition_version: str
    strategy_key: str
    strategy_definition_version: str
    signal_identity: tuple[str, str]
    frequency: ResearchRebalanceFrequency
    current_as_of: datetime
    as_of: datetime
    actions: tuple[ResearchRebalanceAction, ...]
    current_gross_exposure: float
    current_net_exposure: float
    target_gross_exposure: float
    target_net_exposure: float
    turnover: float
    status: ResearchRebalanceStatus


class ResearchRebalanceService:
    """Calculate deterministic portfolio weight transitions without execution semantics."""

    def rebalance(
        self,
        current_portfolio: ResearchPortfolio,
        target_portfolio: ResearchPortfolio,
        definition: ResearchRebalanceDefinition,
        as_of: datetime,
    ) -> ResearchRebalance:
        self._validate_inputs(current_portfolio, target_portfolio, definition, as_of)

        current = {position.security_id: position for position in current_portfolio.positions}
        target = {position.security_id: position for position in target_portfolio.positions}

        if len(current) != len(current_portfolio.positions) or len(target) != len(target_portfolio.positions):
            raise InvalidInputError("Portfolio positions must not contain duplicate security IDs.")

        actions: list[ResearchRebalanceAction] = []
        absolute_deltas = 0.0

        for security_id in sorted(set(current) | set(target)):
            current_position = current.get(security_id)
            target_position = target.get(security_id)
            current_weight = 0.0 if current_position is None else float(current_position.target_weight)
            target_weight = 0.0 if target_position is None else float(target_position.target_weight)
            delta = target_weight - current_weight
            if not isfinite(current_weight) or not isfinite(target_weight) or not isfinite(delta):
                raise InvalidInputError("Rebalance weights and deltas must be finite.")

            if delta == 0.0:
                continue

            action = self._classify(current_weight, target_weight)
            position = target_position or current_position
            assert position is not None
            actions.append(
                ResearchRebalanceAction(
                    symbol=position.symbol.strip().upper(),
                    security_id=security_id,
                    current_weight=current_weight,
                    target_weight=target_weight,
                    weight_delta=delta,
                    action=action,
                )
            )
            absolute_deltas += abs(delta)

        turnover = 0.5 * absolute_deltas
        if not isfinite(turnover):
            raise InvalidInputError("Rebalance turnover must be finite.")

        return ResearchRebalance(
            rebalance_key=definition.rebalance_key,
            rebalance_definition_version=definition.definition_version,
            strategy_key=target_portfolio.strategy_key,
            strategy_definition_version=target_portfolio.strategy_definition_version,
            signal_identity=target_portfolio.signal_identity,
            frequency=definition.frequency,
            current_as_of=current_portfolio.as_of,
            as_of=as_of,
            actions=tuple(actions),
            current_gross_exposure=float(current_portfolio.gross_exposure),
            current_net_exposure=float(current_portfolio.net_exposure),
            target_gross_exposure=float(target_portfolio.gross_exposure),
            target_net_exposure=float(target_portfolio.net_exposure),
            turnover=turnover,
            status=(ResearchRebalanceStatus.REBALANCED if actions else ResearchRebalanceStatus.NO_CHANGES),
        )

    @staticmethod
    def _classify(current_weight: float, target_weight: float) -> ResearchRebalanceActionType:
        if current_weight == 0.0:
            return ResearchRebalanceActionType.ADD
        if target_weight == 0.0:
            return ResearchRebalanceActionType.REMOVE
        if (current_weight < 0.0 < target_weight) or (target_weight < 0.0 < current_weight):
            return ResearchRebalanceActionType.REVERSE
        if abs(target_weight) > abs(current_weight):
            return ResearchRebalanceActionType.INCREASE
        return ResearchRebalanceActionType.REDUCE

    @staticmethod
    def _validate_inputs(
        current_portfolio: ResearchPortfolio,
        target_portfolio: ResearchPortfolio,
        definition: ResearchRebalanceDefinition,
        as_of: datetime,
    ) -> None:
        if not isinstance(current_portfolio, ResearchPortfolio):
            raise InvalidInputError("Rebalancing requires a ResearchPortfolio as current state.")
        if not isinstance(target_portfolio, ResearchPortfolio):
            raise InvalidInputError("Rebalancing requires a ResearchPortfolio as target state.")
        if not isinstance(definition, ResearchRebalanceDefinition):
            raise InvalidInputError("Rebalancing requires a ResearchRebalanceDefinition.")
        if not isinstance(as_of, datetime) or as_of.tzinfo is None:
            raise InvalidInputError("Rebalance as_of must be timezone-aware.")
        if current_portfolio.as_of.tzinfo is None or target_portfolio.as_of.tzinfo is None:
            raise InvalidInputError("Portfolio as_of values must be timezone-aware.")
        if current_portfolio.as_of >= as_of:
            raise InvalidInputError("Current portfolio must precede the rebalance as_of.")
        if target_portfolio.as_of != as_of:
            raise InvalidInputError("Target portfolio as_of must equal the rebalance as_of.")
        if current_portfolio.status.name != "CONSTRUCTED":
            raise InvalidInputError("Rebalancing requires a constructed current portfolio.")
        if target_portfolio.status.name != "CONSTRUCTED":
            raise InvalidInputError("Rebalancing requires a constructed target portfolio.")
        if current_portfolio.strategy_key != target_portfolio.strategy_key or current_portfolio.strategy_definition_version != target_portfolio.strategy_definition_version:
            raise InvalidInputError("Current and target portfolios must use the same strategy identity.")
        if current_portfolio.signal_identity != target_portfolio.signal_identity:
            raise InvalidInputError("Current and target portfolios must use the same signal identity.")
        for portfolio in (current_portfolio, target_portfolio):
            if not isfinite(float(portfolio.gross_exposure)) or not isfinite(float(portfolio.net_exposure)):
                raise InvalidInputError("Portfolio exposures must be finite.")
            for position in portfolio.positions:
                if not isinstance(position.security_id, int):
                    raise InvalidInputError("Portfolio security IDs must be integers.")
                if not isfinite(float(position.target_weight)):
                    raise InvalidInputError("Portfolio position weights must be finite.")
