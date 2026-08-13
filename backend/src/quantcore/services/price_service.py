from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.repositories.price_repository import PriceRepository
from quantcore.repositories.security_repository import SecurityRepository


class PriceService:

    def __init__(self, db: Session):
        self.db = db
        self.client = ProviderFactory.get_provider()

        self.security_repo = SecurityRepository(db)
        self.price_repo = PriceRepository(db)

    def _get_security(
        self,
        symbol: str,
    ):
        symbol = symbol.upper()

        security = self.security_repo.get_by_symbol(
            symbol
        )

        if security is None:
            raise ValueError(
                f"Security '{symbol}' not found. "
                "Run security sync first."
            )

        return security

    def sync_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> int:

        symbol = symbol.upper()

        security = self._get_security(symbol)

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

        security = self._get_security(symbol)

        return self.price_repo.get_for_security(
            security.id
        )