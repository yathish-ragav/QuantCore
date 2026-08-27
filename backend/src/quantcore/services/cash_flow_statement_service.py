from datetime import datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import (
    DataValidationError,
    InvalidInputError,
    ResourceNotFoundError,
)
from quantcore.ingestion.providers.financial_factory import (
    FinancialProviderFactory,
)
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.models.provenance import DataSource
from quantcore.core.enums import FinancialStatementType
from quantcore.processing.validator import DataValidator
from quantcore.repositories.cash_flow_statement_repository import (
    CashFlowStatementRepository,
)
from quantcore.repositories.security_repository import (
    SecurityRepository,
)
from quantcore.repositories.financial_statement_revision_repository import (
    FinancialStatementRevisionRepository,
)
from quantcore.services.financial_statement_revision import (
    FinancialStatementSyncResult,
    apply_statement_data,
    create_revision,
    get_statements_as_of,
    statement_changed,
)


class CashFlowStatementService:

    def __init__(self, db: Session):
        self.db = db

        self.provider = (
            FinancialProviderFactory.get_provider()
        )

        self.security_repo = SecurityRepository(db)

        self.statement_repo = (
            CashFlowStatementRepository(db)
        )
        self.revision_repo = FinancialStatementRevisionRepository(db)

    def get_company_for_symbol(
        self,
        symbol: str,
    ):
        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        security = self.security_repo.get_by_symbol(
            symbol
        )

        company = (
            security.company
            if security is not None
            else None
        )

        if company is None:
            raise ResourceNotFoundError(
                f"Company not found: {symbol}"
            )

        return security, company

    def get_cash_flow_statements(
        self,
        symbol: str,
        as_of: datetime | None = None,
    ):
        _, company = self.get_company_for_symbol(
            symbol
        )

        if as_of is None:
            return self.statement_repo.get_for_company(
                company.id
            )

        return get_statements_as_of(
            self.revision_repo,
            company.id,
            FinancialStatementType.CASH_FLOW,
            as_of,
        )

    def sync_cash_flow_statements(
        self,
        symbol: str,
    ):

        try:
            # -------------------------------------------------
            # 1. Clean and validate symbol.
            # -------------------------------------------------
            symbol = DataCleaner.clean_symbol(
                symbol
            )

            if not symbol:
                raise InvalidInputError(
                    "Symbol must not be empty."
                )

            # -------------------------------------------------
            # 2. Resolve Company identity.
            # -------------------------------------------------
            _, company = (
                self.get_company_for_symbol(symbol)
            )

            # -------------------------------------------------
            # 3. Fetch external financial data.
            # -------------------------------------------------
            raw_statements = (
                self.provider.get_cash_flow_statements(
                    symbol
                )
            )

            # -------------------------------------------------
            # 4. Transform.
            # -------------------------------------------------
            statements = (
                DataTransformer.cash_flow_statements(
                    raw_statements
                )
            )

            # -------------------------------------------------
            # 5. Clean.
            # -------------------------------------------------
            statements = [
                DataCleaner.clean_cash_flow_statement(
                    statement
                )
                for statement in statements
            ]

            # -------------------------------------------------
            # 6. Validate complete dataset before mutation.
            # -------------------------------------------------
            if not DataValidator.validate_cash_flow_statements(
                statements
            ):
                raise DataValidationError(
                    f"Invalid cash flow statement data "
                    f"for '{symbol}'."
                )

            created = 0
            updated = 0
            unchanged = 0
            source = DataSource(self.provider.SOURCE)
            fetched_at = datetime.now(timezone.utc)

            # -------------------------------------------------
            # 7. Reconcile statements.
            # -------------------------------------------------
            for data in statements:

                existing = self.statement_repo.get_by_company_and_date(
                    company.id,
                    data.fiscal_date,
                    data.period_type,
                )

                if existing is None:
                    statement = self.statement_repo.create(
                        company_id=company.id,
                        fiscal_date=data.fiscal_date,
                        period_start=data.period_start,
                        fiscal_year=data.fiscal_year,
                        fiscal_period=data.fiscal_period,
                        period_type=data.period_type,
                        filing_date=data.filing_date,
                        filing_form=data.filing_form,
                        accession_number=data.accession_number,
                        operating_cash_flow=data.operating_cash_flow,
                        capital_expenditure=data.capital_expenditure,
                        free_cash_flow=data.free_cash_flow,
                        investing_cash_flow=data.investing_cash_flow,
                        financing_cash_flow=data.financing_cash_flow,
                        depreciation_and_amortization=data.depreciation_and_amortization,
                        stock_based_compensation=data.stock_based_compensation,
                        dividends_paid=data.dividends_paid,
                        share_repurchases=data.share_repurchases,
                        net_change_in_cash=data.net_change_in_cash,
                        source=source,
                        fetched_at=fetched_at,
                    )
                    self.db.flush()
                    create_revision(
                        self.revision_repo,
                        statement,
                        FinancialStatementType.CASH_FLOW,
                        source,
                        fetched_at,
                    )
                    created += 1
                    continue

                if not statement_changed(existing, data, FinancialStatementType.CASH_FLOW):
                    unchanged += 1
                    continue

                apply_statement_data(existing, data, FinancialStatementType.CASH_FLOW)
                existing.source = source
                existing.fetched_at = fetched_at
                create_revision(
                    self.revision_repo,
                    existing,
                    FinancialStatementType.CASH_FLOW,
                    source,
                    fetched_at,
                )
                updated += 1

            self.db.commit()

            return FinancialStatementSyncResult(
                created=created,
                updated=updated,
                unchanged=unchanged,
                records_processed=len(statements),
            )

        except Exception:
            # -------------------------------------------------
            # Atomic failure semantics.
            # -------------------------------------------------
            self.db.rollback()
            raise
