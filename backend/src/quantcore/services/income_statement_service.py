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
from quantcore.processing.validator import DataValidator
from quantcore.repositories.income_statement_repository import (
    IncomeStatementRepository,
)
from quantcore.repositories.security_repository import (
    SecurityRepository,
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

    def sync_income_statements(
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

            created_statements = []

            # -------------------------------------------------
            # 7. Reconcile statements.
            # -------------------------------------------------
            for data in statements:

                existing = (
                    self.statement_repo
                    .get_by_company_and_date(
                        company.id,
                        data.fiscal_date,
                    )
                )

                if existing is not None:
                    continue

                statement = (
                    self.statement_repo.create(
                        company_id=company.id,
                        fiscal_date=data.fiscal_date,
                        total_revenue=data.total_revenue,
                        gross_profit=data.gross_profit,
                        operating_income=data.operating_income,
                        net_income=data.net_income,
                        eps=data.eps,
                        shares_outstanding=(
                            data.shares_outstanding
                        ),
                    )
                )

                created_statements.append(
                    statement
                )

            # -------------------------------------------------
            # 8. Commit entire operation once.
            # -------------------------------------------------
            self.db.commit()

            return created_statements

        except Exception:
            # -------------------------------------------------
            # Atomic failure semantics.
            # -------------------------------------------------
            self.db.rollback()
            raise