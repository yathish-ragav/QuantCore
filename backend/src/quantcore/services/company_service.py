from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.security_repository import SecurityRepository


class CompanyService:

    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()

        self.security_repo = SecurityRepository(db)
        self.company_repo = CompanyRepository(db)

    def get_company(
        self,
        symbol: str,
    ):

        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        security = self.security_repo.get_by_symbol(
            symbol
        )

        if security is None:
            raise ValueError(
                f"Security '{symbol}' not found. "
                "Run universe sync first."
            )

        company = security.company

        if company is None:
            raise ValueError(
                f"Company for security '{symbol}' "
                "not found."
            )

        return company

    def sync_company(
        self,
        symbol: str,
    ):

        try:
            symbol = DataCleaner.clean_symbol(symbol)

            if not symbol:
                raise ValueError(
                    "Symbol must not be empty."
                )

            security = self.security_repo.get_by_symbol(
                symbol
            )

            if security is None:
                raise ValueError(
                    f"Security '{symbol}' not found. "
                    "Run universe sync first."
                )

            company = security.company

            if company is None:
                raise ValueError(
                    f"Company for security '{symbol}' "
                    "not found."
                )

            raw_data = self.client.get_company_info(
                symbol
            )

            data = DataTransformer.company(
                raw_data
            )

            data = DataCleaner.clean_company(
                data
            )

            if not DataValidator.validate_company(
                data
            ):
                raise ValueError(
                    f"Invalid company data for '{symbol}'."
                )

            if data.symbol != symbol:
                raise ValueError(
                    f"Provider returned symbol "
                    f"'{data.symbol}' for requested "
                    f"symbol '{symbol}'."
                )

            company = self.company_repo.update(
                company=company,
                name=data.name,
                sector=data.sector,
                industry=data.industry,
                country=data.country,
                website=data.website,
                market_cap=data.market_cap,
            )

            self.db.commit()
            self.db.refresh(company)

            return company

        except Exception:
            self.db.rollback()
            raise