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
from quantcore.processing.validator import DataValidator
from quantcore.repositories.cash_flow_statement_repository import (
    CashFlowStatementRepository,
)
from quantcore.repositories.security_repository import (
    SecurityRepository,
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
    ):
        _, company = self.get_company_for_symbol(
            symbol
        )

        return self.statement_repo.get_for_company(
            company.id
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

            created_statements = []
            source = DataSource(self.provider.SOURCE)
            fetched_at = datetime.now(timezone.utc)

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
                        operating_cash_flow=(
                            data.operating_cash_flow
                        ),
                        capital_expenditure=(
                            data.capital_expenditure
                        ),
                        free_cash_flow=data.free_cash_flow,
                        investing_cash_flow=(
                            data.investing_cash_flow
                        ),
                        financing_cash_flow=(
                            data.financing_cash_flow
                        ),
                        depreciation_and_amortization=(
                            data.depreciation_and_amortization
                        ),
                        stock_based_compensation=(
                            data.stock_based_compensation
                        ),
                        dividends_paid=data.dividends_paid,
                        share_repurchases=(
                            data.share_repurchases
                        ),
                        net_change_in_cash=(
                            data.net_change_in_cash
                        ),
                        source=source,
                        fetched_at=fetched_at,
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
