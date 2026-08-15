from sqlalchemy.orm import Session

from quantcore.ingestion.providers.financial_factory import (
    FinancialProviderFactory,
)
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.company_repository import (
    CompanyRepository,
)
from quantcore.repositories.income_statement_repository import (
    IncomeStatementRepository,
)


class IncomeStatementService:

    def __init__(self, db: Session):
        self.db = db

        self.provider = (
            FinancialProviderFactory.get_provider()
        )

        self.company_repo = CompanyRepository(db)

        self.statement_repo = (
            IncomeStatementRepository(db)
        )

    def sync_income_statements(
        self,
        symbol: str,
    ):

        try:
            symbol = DataCleaner.clean_symbol(
                symbol
            )

            if not symbol:
                raise ValueError(
                    "Symbol must not be empty."
                )

            company = (
                self.company_repo.get_by_symbol(
                    symbol
                )
            )

            if company is None:
                raise ValueError(
                    f"Company not found: {symbol}"
                )

            raw_statements = (
                self.provider.get_income_statements(
                    symbol
                )
            )

            statements = (
                DataTransformer.income_statements(
                    raw_statements
                )
            )

            statements = [
                DataCleaner.clean_income_statement(
                    statement
                )
                for statement in statements
            ]

            if not DataValidator.validate_income_statements(
                statements
            ):
                raise ValueError(
                    f"Invalid income statement data "
                    f"for '{symbol}'."
                )

            created_statements = []

            for data in statements:

                existing = (
                    self.statement_repo
                    .get_by_company_and_date(
                        company.id,
                        data.fiscal_date,
                    )
                )

                if existing:
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

            self.statement_repo.commit()

            return created_statements

        except Exception:
            self.db.rollback()
            raise