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
from quantcore.models.provenance import DataSource
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.balance_sheet_repository import (
    BalanceSheetRepository,
)
from quantcore.repositories.security_repository import SecurityRepository


class BalanceSheetService:
    def __init__(self, db: Session):
        self.db = db
        self.provider = FinancialProviderFactory.get_provider()
        self.security_repo = SecurityRepository(db)
        self.statement_repo = BalanceSheetRepository(db)

    def get_company_for_symbol(self, symbol: str):
        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        security = self.security_repo.get_by_symbol(symbol)
        company = security.company if security is not None else None

        if company is None:
            raise ResourceNotFoundError(
                f"Company not found: {symbol}"
            )

        return security, company

    def get_balance_sheets(self, symbol: str):
        _, company = self.get_company_for_symbol(symbol)

        return self.statement_repo.get_for_company(company.id)

    def sync_balance_sheets(self, symbol: str):
        try:
            symbol = DataCleaner.clean_symbol(symbol)

            if not symbol:
                raise InvalidInputError(
                    "Symbol must not be empty."
                )

            _, company = self.get_company_for_symbol(symbol)

            raw_statements = self.provider.get_balance_sheets(symbol)

            statements = DataTransformer.balance_sheets(raw_statements)

            statements = [
                DataCleaner.clean_balance_sheet(statement)
                for statement in statements
            ]

            if not DataValidator.validate_balance_sheets(statements):
                raise DataValidationError(
                    f"Invalid balance sheet data for '{symbol}'."
                )

            created_statements = []
            source = DataSource(self.provider.SOURCE)
            fetched_at = datetime.now(timezone.utc)

            for data in statements:
                existing = self.statement_repo.get_by_company_and_date(
                    company.id,
                    data.fiscal_date,
                )

                if existing is not None:
                    continue

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
                    cash_and_cash_equivalents=(
                        data.cash_and_cash_equivalents
                    ),
                    short_term_investments=(
                        data.short_term_investments
                    ),
                    accounts_receivable=data.accounts_receivable,
                    inventory=data.inventory,
                    total_current_assets=(
                        data.total_current_assets
                    ),
                    property_plant_equipment_net=(
                        data.property_plant_equipment_net
                    ),
                    goodwill=data.goodwill,
                    intangible_assets=data.intangible_assets,
                    total_assets=data.total_assets,
                    accounts_payable=data.accounts_payable,
                    short_term_debt=data.short_term_debt,
                    total_current_liabilities=(
                        data.total_current_liabilities
                    ),
                    long_term_debt=data.long_term_debt,
                    total_liabilities=data.total_liabilities,
                    total_equity=data.total_equity,
                    retained_earnings=data.retained_earnings,
                    total_debt=data.total_debt,
                    net_debt=data.net_debt,
                    working_capital=data.working_capital,
                    source=source,
                    fetched_at=fetched_at,
                )

                created_statements.append(statement)

            self.db.commit()

            return created_statements

        except Exception:
            self.db.rollback()
            raise
