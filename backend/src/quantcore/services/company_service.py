from datetime import datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import (
    DataValidationError,
    InvalidInputError,
    ResourceNotFoundError,
)
from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.models.provenance import CompanyField, DataSource
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.company_field_provenance_repository import (
    CompanyFieldProvenanceRepository,
)
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.security_repository import SecurityRepository


# SEC is the authoritative source for issuer identity. Other providers
# must not silently replace these fields after SEC has established them.
AUTHORITATIVE_COMPANY_FIELDS = {
    CompanyField.CIK: DataSource.SEC,
    CompanyField.NAME: DataSource.SEC,
}


class CompanyService:

    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()

        self.security_repo = SecurityRepository(db)
        self.company_repo = CompanyRepository(db)
        self.provenance_repo = CompanyFieldProvenanceRepository(db)

    def get_company(
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

        if security is None:
            raise ResourceNotFoundError(
                f"Security '{symbol}' not found. "
                "Run universe sync first."
            )

        company = security.company

        if company is None:
            raise ResourceNotFoundError(
                f"Company for security '{symbol}' "
                "not found."
            )

        return company

    def _can_write_company_field(
        self,
        company_id: int,
        field_name: CompanyField,
        source: DataSource,
    ) -> bool:
        ownership = self.provenance_repo.get(
            company_id,
            field_name,
        )

        if ownership is None:
            return True

        if ownership.source == source:
            return True

        authoritative_source = AUTHORITATIVE_COMPANY_FIELDS.get(
            field_name
        )

        if authoritative_source == ownership.source:
            return False

        if authoritative_source == source:
            return True

        # Conservative default: an existing owner is never silently
        # replaced unless the incoming source is explicitly authoritative.
        return False

    def sync_company(
        self,
        symbol: str,
    ):
        try:
            symbol = DataCleaner.clean_symbol(symbol)

            if not symbol:
                raise InvalidInputError(
                    "Symbol must not be empty."
                )

            security = self.security_repo.get_by_symbol(
                symbol
            )

            if security is None:
                raise ResourceNotFoundError(
                    f"Security '{symbol}' not found. "
                    "Run universe sync first."
                )

            company = security.company

            if company is None:
                raise ResourceNotFoundError(
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
                raise DataValidationError(
                    f"Invalid company data for '{symbol}'."
                )

            if data.symbol != symbol:
                raise DataValidationError(
                    f"Provider returned symbol "
                    f"'{data.symbol}' for requested "
                    f"symbol '{symbol}'."
                )

            source = DataSource(self.client.SOURCE)
            fetched_at = datetime.now(timezone.utc)

            incoming_fields = {
                CompanyField.NAME: data.name,
                CompanyField.SECTOR: data.sector,
                CompanyField.INDUSTRY: data.industry,
                CompanyField.COUNTRY: data.country,
                CompanyField.WEBSITE: data.website,
                CompanyField.MARKET_CAP: data.market_cap,
            }

            accepted_fields = {
                field: value
                for field, value in incoming_fields.items()
                if self._can_write_company_field(
                    company.id,
                    field,
                    source,
                )
            }

            values = {
                "name": company.name,
                "sector": company.sector,
                "industry": company.industry,
                "country": company.country,
                "website": company.website,
                "market_cap": company.market_cap,
                "cik": company.cik,
            }

            for field, value in accepted_fields.items():
                values[field.value] = value

            company = self.company_repo.update(
                company=company,
                name=values["name"],
                sector=values["sector"],
                industry=values["industry"],
                country=values["country"],
                website=values["website"],
                market_cap=values["market_cap"],
                cik=values["cik"],
            )

            for field in accepted_fields:
                self.provenance_repo.upsert(
                    company_id=company.id,
                    field_name=field,
                    source=source,
                    fetched_at=fetched_at,
                )

            self.db.commit()
            self.db.refresh(company)

            return company

        except Exception:
            self.db.rollback()
            raise
