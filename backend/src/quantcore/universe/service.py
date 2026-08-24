from datetime import datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import DataValidationError
from quantcore.models.provenance import CompanyField, DataSource
from quantcore.models.security import SecurityStatus
from quantcore.repositories.company_field_provenance_repository import (
    CompanyFieldProvenanceRepository,
)
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.security_identifier_history_repository import (
    SecurityIdentifierHistoryRepository,
)
from quantcore.repositories.security_repository import SecurityRepository
from quantcore.universe.filters import DEFAULT_US_EXCHANGES, filter_us_equities
from quantcore.universe.normalizer import normalize_companies
from quantcore.universe.providers.sec import SECUniverseProvider


class UniverseService:

    def __init__(self, db: Session):
        self.db = db
        self.provider = SECUniverseProvider()
        self.company_repo = CompanyRepository(db)
        self.security_repo = SecurityRepository(db)
        self.provenance_repo = CompanyFieldProvenanceRepository(db)
        self.identifier_history_repo = SecurityIdentifierHistoryRepository(db)

    def sync(self) -> int:
        companies = self.provider.fetch()
        companies = normalize_companies(companies)
        companies = filter_us_equities(companies)

        if not companies:
            return 0

        symbol_to_cik: dict[tuple[str, str], str] = {}

        for company in companies:
            identity = (company.symbol, company.exchange)
            existing_cik = symbol_to_cik.get(identity)

            if existing_cik is not None and existing_cik != company.cik:
                raise DataValidationError(
                    f"Security symbol '{company.symbol}' "
                    f"is associated with multiple companies: "
                    f"{existing_cik} and {company.cik}."
                )

            symbol_to_cik[identity] = company.cik

        synced = 0
        fetched_at = datetime.now(timezone.utc)

        try:
            companies_by_cik: dict[str, list] = {}
            for company in companies:
                companies_by_cik.setdefault(company.cik, []).append(company)

            ciks = list(companies_by_cik.keys())
            existing_by_cik = {
                company.cik: company
                for company in self.company_repo.get_by_ciks(ciks)
            }
            synced_companies_by_cik = {}

            for cik, universe_companies in companies_by_cik.items():
                representative = universe_companies[0]
                company = existing_by_cik.get(cik)

                if company is None:
                    company = self.company_repo.create(
                        cik=cik,
                        name=representative.name,
                        sector="",
                        industry="",
                        country="",
                        website="",
                        market_cap=None,
                    )
                else:
                    company.cik = cik
                    company.name = representative.name

                synced_companies_by_cik[cik] = company
                synced += len(universe_companies)

            self.db.flush()

            for company in synced_companies_by_cik.values():
                self.provenance_repo.upsert(
                    company_id=company.id,
                    field_name=CompanyField.CIK,
                    source=DataSource.SEC,
                    fetched_at=fetched_at,
                )
                self.provenance_repo.upsert(
                    company_id=company.id,
                    field_name=CompanyField.NAME,
                    source=DataSource.SEC,
                    fetched_at=fetched_at,
                )

            company_ids = [company.id for company in synced_companies_by_cik.values()]
            existing_securities = self.security_repo.get_by_company_ids(company_ids)
            existing_by_identity = {
                (security.company_id, security.symbol, security.exchange): security
                for security in existing_securities
            }
            current_identities = set()

            for universe_company in companies:
                company = synced_companies_by_cik[universe_company.cik]
                identity = (
                    company.id,
                    universe_company.symbol,
                    universe_company.exchange,
                )
                current_identities.add(identity)

                security = existing_by_identity.get(identity)

                if security is None:
                    security = self.security_repo.create(
                        company_id=company.id,
                        symbol=universe_company.symbol,
                        exchange=universe_company.exchange,
                    )
                    security.status = SecurityStatus.ACTIVE
                    security.first_seen_at = fetched_at
                    if security.id is None:
                        self.db.flush()
                else:
                    security.status = SecurityStatus.ACTIVE

                security.last_seen_at = fetched_at
                security.source = DataSource.SEC
                security.fetched_at = fetched_at

                self.identifier_history_repo.upsert(
                    security_id=security.id,
                    symbol=universe_company.symbol,
                    exchange=universe_company.exchange,
                    observed_at=fetched_at,
                )
                self.identifier_history_repo.mark_not_current(
                    security_id=security.id,
                    except_symbol=universe_company.symbol,
                    except_exchange=universe_company.exchange,
                )

            # The SEC source is a current ticker/exchange association feed.
            # Mark previously-known listings in QuantCore's managed exchange
            # scope that disappeared from this snapshot inactive rather than
            # deleting their historical identity.
            managed_securities = self.security_repo.get_active_by_exchanges(
                list(DEFAULT_US_EXCHANGES)
            )
            for security in managed_securities:
                identity = (security.company_id, security.symbol, security.exchange)
                if identity not in current_identities:
                    security.status = SecurityStatus.INACTIVE
                    self.identifier_history_repo.mark_all_not_current(
                        security.id
                    )

            self.db.commit()
            return synced

        except Exception:
            self.db.rollback()
            raise
