from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from quantcore.core.enums import FinancialPeriodType, FinancialStatementType
from quantcore.models.income_statement import IncomeStatement
from quantcore.models.cash_flow_statement import CashFlowStatement
from quantcore.models.provenance import DataSource
from quantcore.repositories.cash_flow_statement_repository import CashFlowStatementRepository
from quantcore.repositories.financial_statement_revision_repository import (
    FinancialStatementRevisionRepository,
)
from quantcore.repositories.income_statement_repository import IncomeStatementRepository
from quantcore.services.financial_statement_revision import create_revision


INCOME_ADDITIVE_FIELDS = (
    "total_revenue",
    "gross_profit",
    "operating_income",
    "net_income",
)
CASH_FLOW_ADDITIVE_FIELDS = (
    "operating_cash_flow",
    "capital_expenditure",
    "investing_cash_flow",
    "financing_cash_flow",
    "depreciation_and_amortization",
    "stock_based_compensation",
    "dividends_paid",
    "share_repurchases",
    "net_change_in_cash",
)


class FinancialPeriodMaterializer:
    """Materialize deterministic quarterly Q4 residuals and TTM statements.

    This service has no external-provider responsibility. It only derives
    observations from already-persisted financial statements and revisions.
    Every derived revision inherits a knowledge boundary from its inputs rather
    than from the time the materializer happens to execute.
    """

    def __init__(self, db: Session):
        self.db = db
        self.revision_repo = FinancialStatementRevisionRepository(db)
        self.income_repo = IncomeStatementRepository(db)
        self.cash_flow_repo = CashFlowStatementRepository(db)

    def materialize_company(self, company_id: int) -> int:
        if company_id <= 0:
            raise ValueError("company_id must be greater than zero.")

        now = datetime.now(timezone.utc)
        created_or_updated = 0
        created_or_updated += self._materialize_family(
            company_id,
            FinancialStatementType.INCOME,
            now=now,
        )
        created_or_updated += self._materialize_family(
            company_id,
            FinancialStatementType.CASH_FLOW,
            now=now,
        )
        return created_or_updated

    def _materialize_family(
        self,
        company_id: int,
        statement_type: FinancialStatementType,
        *,
        now: datetime,
    ) -> int:
        revisions = self.revision_repo.get_latest_for_company_as_of(
            company_id,
            statement_type,
            now,
        )
        quarters = sorted(
            (
                revision
                for revision in revisions
                if revision.period_type is FinancialPeriodType.QUARTERLY
            ),
            key=lambda revision: revision.fiscal_date,
        )
        annuals = sorted(
            (
                revision
                for revision in revisions
                if revision.period_type is FinancialPeriodType.ANNUAL
            ),
            key=lambda revision: revision.fiscal_date,
        )

        changed = 0
        for annual in annuals:
            q4_inputs = self._find_q4_inputs(annual, quarters)
            if q4_inputs is None:
                continue
            q4_revision = self._materialize_q4(
                company_id,
                statement_type,
                annual,
                q4_inputs,
            )
            if q4_revision is not None:
                changed += 1

        # Re-read latest revisions because Q4 materialization may have created
        # or revised quarterly observations. Every historical four-quarter
        # window gets its own TTM row; this is required for PIT research.
        revisions = self.revision_repo.get_latest_for_company_as_of(
            company_id,
            statement_type,
            now,
        )
        quarters = sorted(
            (
                revision
                for revision in revisions
                if revision.period_type is FinancialPeriodType.QUARTERLY
            ),
            key=lambda revision: revision.fiscal_date,
        )

        for index in range(3, len(quarters)):
            window = quarters[index - 3 : index + 1]
            if not self._quarters_contiguous(window):
                continue
            if self._materialize_ttm(company_id, statement_type, window):
                changed += 1

        return changed

    @staticmethod
    def _quarters_contiguous(window) -> bool:
        if len(window) != 4:
            return False
        for previous, current in zip(window, window[1:]):
            if previous.fiscal_date + timedelta(days=1) != current.period_start:
                return False
        return True

    @classmethod
    def _find_q4_inputs(cls, annual, quarters):
        same_year = [
            revision
            for revision in quarters
            if revision.fiscal_date < annual.fiscal_date
            and revision.fiscal_year == annual.fiscal_year
        ]
        if len(same_year) < 3:
            return None
        candidate = same_year[-3:]
        if not cls._quarters_contiguous(candidate):
            return None
        first = candidate[0]
        third = candidate[-1]
        if first.period_start != annual.period_start:
            return None
        if third.fiscal_date >= annual.fiscal_date:
            return None
        return tuple(candidate)

    def _materialize_q4(
        self,
        company_id: int,
        statement_type: FinancialStatementType,
        annual,
        quarters,
    ):
        if statement_type is FinancialStatementType.INCOME:
            repo = self.income_repo
            values = {
                field: self._residual(getattr(annual, field), [getattr(q, field) for q in quarters])
                for field in INCOME_ADDITIVE_FIELDS
            }
            values.update({
                "eps": None,
                "shares_outstanding": None,
                "weighted_average_shares_outstanding": None,
            })
        else:
            repo = self.cash_flow_repo
            values = {
                field: self._residual(getattr(annual, field), [getattr(q, field) for q in quarters])
                for field in CASH_FLOW_ADDITIVE_FIELDS
            }
            if values["operating_cash_flow"] is not None and values["capital_expenditure"] is not None:
                values["free_cash_flow"] = (
                    values["operating_cash_flow"] - values["capital_expenditure"]
                )
            else:
                values["free_cash_flow"] = None

        source_reference = (
            f"DERIVED_Q4:{statement_type.value}:"
            f"{annual.id}:" + ":".join(str(item.id) for item in quarters)
        )
        fiscal_date = annual.fiscal_date
        existing = repo.get_by_company_and_date(
            company_id,
            fiscal_date,
            FinancialPeriodType.QUARTERLY,
        )
        source = DataSource.SEC
        known_at = max(
            [annual.known_at, *(item.known_at for item in quarters)]
        )
        fetched_at = max(
            (getattr(item, "fetched_at", None) for item in (annual, *quarters)),
            default=None,
        )
        payload = {
            "company_id": company_id,
            "fiscal_date": fiscal_date,
            "period_start": quarters[-1].fiscal_date + timedelta(days=1),
            "fiscal_year": annual.fiscal_year,
            "fiscal_period": "Q4",
            "period_type": FinancialPeriodType.QUARTERLY,
            "filing_date": annual.filing_date,
            "filing_form": annual.filing_form,
            "accession_number": annual.accession_number,
            "source": source,
            "fetched_at": fetched_at,
            "source_reference": source_reference,
            **values,
        }

        if existing is None:
            statement = repo.create(**payload)
            self.db.flush()
            create_revision(
                self.revision_repo,
                statement,
                statement_type,
                source,
                known_at,
                revision_number=1,
            )
            return statement

        if not self._row_matches(existing, payload):
            for key, value in payload.items():
                if key != "company_id":
                    setattr(existing, key, value)
            revision_number = self.revision_repo.get_next_revision_number(
                statement_type, existing.id
            )
            create_revision(
                self.revision_repo,
                existing,
                statement_type,
                source,
                known_at,
                revision_number=revision_number,
            )
            return existing
        return None

    def _materialize_ttm(
        self,
        company_id: int,
        statement_type: FinancialStatementType,
        window,
    ) -> bool:
        latest = window[-1]
        fiscal_date = latest.fiscal_date
        if statement_type is FinancialStatementType.INCOME:
            repo = self.income_repo
            additive_fields = INCOME_ADDITIVE_FIELDS
            values = {
                field: self._sum_field(window, field)
                for field in additive_fields
            }
            values.update({
                "eps": None,
                "shares_outstanding": None,
                "weighted_average_shares_outstanding": None,
            })
        else:
            repo = self.cash_flow_repo
            values = {
                field: self._sum_field(window, field)
                for field in CASH_FLOW_ADDITIVE_FIELDS
            }
            if values["operating_cash_flow"] is not None and values["capital_expenditure"] is not None:
                values["free_cash_flow"] = (
                    values["operating_cash_flow"] - values["capital_expenditure"]
                )
            else:
                values["free_cash_flow"] = None

        source_reference = (
            f"TTM:{statement_type.value}:" + ":".join(str(item.id) for item in window)
        )
        known_at = max(item.known_at for item in window)
        fetched_at = max(
            (getattr(item, "fetched_at", None) for item in window),
            default=None,
        )
        payload = {
            "company_id": company_id,
            "fiscal_date": fiscal_date,
            "period_start": window[0].period_start,
            "fiscal_year": latest.fiscal_year,
            "fiscal_period": "TTM",
            "period_type": FinancialPeriodType.TTM,
            "filing_date": None,
            "filing_form": None,
            "accession_number": None,
            "source": DataSource.SEC,
            "fetched_at": fetched_at,
            "source_reference": source_reference,
            **values,
        }
        repo = self.income_repo if statement_type is FinancialStatementType.INCOME else self.cash_flow_repo
        existing = repo.get_by_company_and_date(
            company_id,
            fiscal_date,
            FinancialPeriodType.TTM,
        )
        if existing is None:
            statement = repo.create(**payload)
            self.db.flush()
            create_revision(
                self.revision_repo,
                statement,
                statement_type,
                DataSource.SEC,
                known_at,
                revision_number=1,
            )
            return True

        if not self._row_matches(existing, payload):
            for key, value in payload.items():
                if key != "company_id":
                    setattr(existing, key, value)
            revision_number = self.revision_repo.get_next_revision_number(
                statement_type, existing.id
            )
            create_revision(
                self.revision_repo,
                existing,
                statement_type,
                DataSource.SEC,
                known_at,
                revision_number=revision_number,
            )
            return True
        return False

    @staticmethod
    def _sum_field(window, field: str):
        values = [getattr(item, field, None) for item in window]
        if any(value is None for value in values):
            return None
        return float(sum(values))

    @staticmethod
    def _residual(annual_value, quarter_values):
        if annual_value is None or any(value is None for value in quarter_values):
            return None
        return float(annual_value) - float(sum(quarter_values))

    @staticmethod
    def _row_matches(existing, payload: dict) -> bool:
        for key, value in payload.items():
            if key == "company_id":
                continue
            if getattr(existing, key, None) != value:
                return False
        return True
