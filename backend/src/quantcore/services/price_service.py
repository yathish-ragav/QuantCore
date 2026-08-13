from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.price_repository import PriceRepository
from quantcore.repositories.security_repository import SecurityRepository


class PriceService:

    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()

        self.company_repo = CompanyRepository(db)
        self.security_repo = SecurityRepository(db)
        self.price_repo = PriceRepository(db)

    def sync_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> int:

        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(
                f"Company '{symbol}' not found. "
                "Run company sync first."
            )

        security = (
            self.security_repo.get_by_company_and_symbol(
                company.id,
                symbol,
            )
        )

        if security is None:
            raise ValueError(
                f"Security '{symbol}' not found. "
                "Run security sync first."
            )

        history = self.client.get_price_history(
            symbol,
            period=period,
        )

        inserted = 0

        for data in history:

            existing = (
                self.price_repo.get_by_security_and_date(
                    security.id,
                    data.date,
                )
            )

            if existing:
                continue

            self.price_repo.create(
                security_id=security.id,
                date=data.date,
                open=data.open,
                high=data.high,
                low=data.low,
                close=data.close,
                volume=data.volume,
                dividends=data.dividends,
                stock_splits=data.stock_splits,
            )

            inserted += 1

        self.price_repo.commit()

        return inserted

    def get_price_history(
        self,
        symbol: str,
    ):

        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(
                f"Company '{symbol}' not found."
            )

        security = (
            self.security_repo.get_by_company_and_symbol(
                company.id,
                symbol,
            )
        )

        if security is None:
            raise ValueError(
                f"Security '{symbol}' not found."
            )

        return self.price_repo.get_for_security(
            security.id
        )