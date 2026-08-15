from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.company_repository import CompanyRepository


class CompanyService:

    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()
        self.repo = CompanyRepository(db)

    def sync_company(self, symbol: str):

        try:
            symbol = DataCleaner.clean_symbol(symbol)

            if not symbol:
                raise ValueError(
                    "Symbol must not be empty."
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

            existing = self.repo.get_by_symbol(
                symbol
            )

            if existing:

                company = self.repo.update(
                    company=existing,
                    name=data.name,
                    sector=data.sector,
                    industry=data.industry,
                    country=data.country,
                    website=data.website,
                    market_cap=data.market_cap,
                )

            else:

                company = self.repo.create(
                    symbol=data.symbol,
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