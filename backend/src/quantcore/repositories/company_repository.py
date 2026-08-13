from sqlalchemy.orm import Session

from quantcore.models.company import Company


class CompanyRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_symbol(self, symbol: str):
        return (
            self.db.query(Company)
            .filter(Company.symbol == symbol)
            .first()
        )

    def get_by_cik(self, cik: str):
        return (
            self.db.query(Company)
            .filter(Company.cik == cik)
            .first()
        )

    def create(
        self,
        symbol: str,
        name: str,
        sector: str,
        industry: str,
        country: str,
        website: str,
        market_cap: int | None,
        cik: str = "",
        exchange: str = "",
    ):
        company = Company(
            cik=cik,
            symbol=symbol,
            name=name,
            sector=sector,
            industry=industry,
            country=country,
            website=website,
            market_cap=market_cap,
            exchange=exchange,
        )

        self.db.add(company)

        return company

    def update(
        self,
        company: Company,
        name: str,
        sector: str,
        industry: str,
        country: str,
        website: str,
        market_cap: int | None,
        cik: str | None = None,
        exchange: str | None = None,
    ):
        company.name = name
        company.sector = sector
        company.industry = industry
        company.country = country
        company.website = website
        company.market_cap = market_cap

        if cik is not None:
            company.cik = cik

        if exchange is not None:
            company.exchange = exchange

        return company