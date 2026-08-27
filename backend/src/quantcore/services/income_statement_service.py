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
from quantcore.repositories.income_statement_repository import (
    IncomeStatementRepository,
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


class IncomeStatementService:

    def __init__(self, db: Session):
        self.db = db

        self.provider = (
            FinancialProviderFactory.get_provider()
        )

        self.security_repo = SecurityRepository(db)

        self.statement_repo = (
            IncomeStatementRepository(db)
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

    def get_income_statements(
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
            FinancialStatementType.INCOME,
            as_of,
        )

    def sync_income_statements(
        self,
        symbol: str,
    ) -> FinancialStatementSyncResult:

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
                self.provider.get_income_statements(
                    symbol
                )
            )

            # -------------------------------------------------
            # 4. Transform.
            # -------------------------------------------------
            statements = (
                DataTransformer.income_statements(
                    raw_statements
                )
            )

            # -------------------------------------------------
            # 5. Clean.
            # -------------------------------------------------
            statements = [
                DataCleaner.clean_income_statement(
                    statement
                )
                for statement in statements
            ]

            # -------------------------------------------------
            # 6. Validate complete dataset before mutation.
            # -------------------------------------------------
            if not DataValidator.validate_income_statements(
                statements
            ):
                raise DataValidationError(
                    f"Invalid income statement data "
                    f"for '{symbol}'."
                )

            created = 0
            updated = 0
            unchanged = 0
            source = DataSource(self.provider.SOURCE)
            fetched_at = datetime.now(timezone.utc)

            # -------------------------------------------------
            # 7. Reconcile statements and preserve revisions.
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
                        total_revenue=data.total_revenue,
                        gross_profit=data.gross_profit,
                        operating_income=data.operating_income,
                        net_income=data.net_income,
                        eps=data.eps,
                        shares_outstanding=data.shares_outstanding,
                        source=source,
                        fetched_at=fetched_at,
                    )
                    self.db.flush()
                    create_revision(
                        self.revision_repo,
                        statement,
                        FinancialStatementType.INCOME,
                        source,
                        fetched_at,
                    )
                    created += 1
                    continue

                if not statement_changed(existing, data, FinancialStatementType.INCOME):
                    unchanged += 1
                    continue

                apply_statement_data(existing, data, FinancialStatementType.INCOME)
                existing.source = source
                existing.fetched_at = fetched_at
                create_revision(
                    self.revision_repo,
                    existing,
                    FinancialStatementType.INCOME,
                    source,
                    fetched_at,
                )
                updated += 1

            # -------------------------------------------------
            # 8. Commit entire operation once.
            # -------------------------------------------------
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