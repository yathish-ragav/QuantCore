from sqlalchemy.orm import Session

from quantcore.ingestion.yfinance import YahooFinanceClient
from quantcore.repositories.company_repository import CompanyRepository
from quantcore.repositories.price_repository import PriceRepository


class PriceService:
    def __init__(self, db: Session):
        self.db = db
        self.client = YahooFinanceClient()
        self.company_repo = CompanyRepository(db)
        self.price_repo = PriceRepository(db)

    def sync_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> int:

        company = self.company_repo.get_by_symbol(symbol)

        if company is None:
            raise ValueError(
                f"Company '{symbol}' not found. Run company sync first."
            )

        history = self.client.get_price_history(
            symbol,
            period=period,
        )

        inserted = 0

        for data in history:

            existing = self.price_repo.get_by_company_and_date(
                company.id,
                data.date,
            )

            if existing:
                continue

            self.price_repo.create(
                company_id=company.id,
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