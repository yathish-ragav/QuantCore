from dataclasses import dataclass

from quantcore.core.enums import FinancialPeriodType
from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.pit_alignment_service import PITAlignedSnapshot
from quantcore.services.research_observation_definition_service import (
    ResearchObservationDefinition,
    ResearchObservationValue,
)


@dataclass(frozen=True)
class _StatementMetricDefinition:
    """Versioned deterministic ratio over one PIT-selected statement row."""

    observation_key: str
    definition_version: str
    unit: str
    statement_family: str
    period_type: FinancialPeriodType
    numerator_field: str
    denominator_field: str
    source_attr: str
    description: str

    def _select_source(self, snapshot: PITAlignedSnapshot):
        rows = tuple(getattr(snapshot, self.source_attr))
        candidates = tuple(
            row
            for row in rows
            if getattr(row, "period_type", None) == self.period_type
        )
        if not candidates:
            raise ResourceNotFoundError(
                f"No {self.statement_family} {self.period_type.value} observation "
                f"available for {self.observation_key}."
            )
        return max(
            candidates,
            key=lambda row: (
                getattr(row, "fiscal_date", None),
                getattr(row, "known_at", None),
                getattr(row, "revision_number", None),
                getattr(row, "id", None),
            ),
        )

    def compute(self, snapshot: PITAlignedSnapshot) -> ResearchObservationValue:
        source = self._select_source(snapshot)
        numerator = getattr(source, self.numerator_field, None)
        denominator = getattr(source, self.denominator_field, None)
        if numerator is None or denominator is None:
            raise ResourceNotFoundError(
                f"Required inputs for {self.observation_key} are unavailable."
            )
        if denominator == 0:
            raise InvalidInputError(
                f"Cannot compute {self.observation_key}: denominator is zero."
            )
        return ResearchObservationValue(
            value_numeric=float(numerator) / float(denominator),
            unit=self.unit,
            input_manifest=_manifest(self, source),
        )


@dataclass(frozen=True)
class _FreeCashFlowMarginDefinition:
    observation_key: str = "fcf_margin"
    definition_version: str = "1"

    def compute(self, snapshot: PITAlignedSnapshot) -> ResearchObservationValue:
        income = _select_latest(snapshot.income_statements, FinancialPeriodType.TTM)
        cash_flow = _select_latest(snapshot.cash_flow_statements, FinancialPeriodType.TTM)
        revenue = getattr(income, "total_revenue", None)
        free_cash_flow = getattr(cash_flow, "free_cash_flow", None)
        if income.fiscal_date != cash_flow.fiscal_date:
            raise InvalidInputError(
                "Cannot compute fcf_margin: TTM income and cash-flow periods do not match."
            )
        if revenue is None or free_cash_flow is None:
            raise ResourceNotFoundError(
                "Required inputs for fcf_margin are unavailable."
            )
        if revenue == 0:
            raise InvalidInputError("Cannot compute fcf_margin: denominator is zero.")
        return ResearchObservationValue(
            value_numeric=float(free_cash_flow) / float(revenue),
            unit="ratio",
            input_manifest={
                "metric": {
                    "observation_key": self.observation_key,
                    "definition_version": self.definition_version,
                    "description": "TTM free cash flow divided by TTM total revenue "
                    "from the same fiscal period.",
                },
                "source": {
                    "income_statement_id": getattr(income, "id", None),
                    "income_statement_statement_id": getattr(income, "statement_id", None),
                    "cash_flow_statement_id": getattr(cash_flow, "id", None),
                    "cash_flow_statement_statement_id": getattr(cash_flow, "statement_id", None),
                    "income_fiscal_date": income.fiscal_date.isoformat(),
                    "cash_flow_fiscal_date": cash_flow.fiscal_date.isoformat(),
                    "period_type": FinancialPeriodType.TTM.value,
                    "income_known_at": income.known_at.isoformat(),
                    "cash_flow_known_at": cash_flow.known_at.isoformat(),
                },
                "formula": {
                    "numerator": "cash_flow_statement.free_cash_flow",
                    "denominator": "income_statement.total_revenue",
                },
            },
        )


def _select_latest(rows, period_type):
    candidates = tuple(
        row for row in tuple(rows) if getattr(row, "period_type", None) == period_type
    )
    if not candidates:
        raise ResourceNotFoundError(
            f"No financial statement {period_type.value} observation available."
        )
    return max(
        candidates,
        key=lambda row: (
            getattr(row, "fiscal_date", None),
            getattr(row, "known_at", None),
            getattr(row, "revision_number", None),
            getattr(row, "id", None),
        ),
    )


def _manifest(definition: _StatementMetricDefinition, source) -> dict:
    return {
        "metric": {
            "observation_key": definition.observation_key,
            "definition_version": definition.definition_version,
            "description": definition.description,
        },
        "source": {
            "statement_family": definition.statement_family,
            "statement_id": getattr(source, "statement_id", None),
            "revision_id": getattr(source, "id", None),
            "revision_number": getattr(source, "revision_number", None),
            "fiscal_date": source.fiscal_date.isoformat(),
            "period_type": definition.period_type.value,
            "known_at": source.known_at.isoformat(),
        },
        "formula": {
            "numerator": definition.numerator_field,
            "denominator": definition.denominator_field,
        },
    }


CANONICAL_RESEARCH_METRICS: tuple[ResearchObservationDefinition, ...] = (
    _StatementMetricDefinition(
        observation_key="net_margin",
        definition_version="1",
        unit="ratio",
        statement_family="income_statement",
        period_type=FinancialPeriodType.TTM,
        numerator_field="net_income",
        denominator_field="total_revenue",
        source_attr="income_statements",
        description="TTM net income divided by TTM total revenue.",
    ),
    _StatementMetricDefinition(
        observation_key="operating_margin",
        definition_version="1",
        unit="ratio",
        statement_family="income_statement",
        period_type=FinancialPeriodType.TTM,
        numerator_field="operating_income",
        denominator_field="total_revenue",
        source_attr="income_statements",
        description="TTM operating income divided by TTM total revenue.",
    ),
    _FreeCashFlowMarginDefinition(),
    _StatementMetricDefinition(
        observation_key="debt_to_equity",
        definition_version="1",
        unit="ratio",
        statement_family="balance_sheet",
        period_type=FinancialPeriodType.INSTANT,
        numerator_field="total_debt",
        denominator_field="total_equity",
        source_attr="balance_sheets",
        description="Latest PIT-known total debt divided by total equity.",
    ),
)


def get_canonical_research_metric_definitions() -> tuple[ResearchObservationDefinition, ...]:
    """Return the immutable canonical research metric definitions."""
    return CANONICAL_RESEARCH_METRICS
