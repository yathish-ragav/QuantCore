from sqlalchemy.orm import Session

from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
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
                "Run security sync first."
            )

        return security

    def sync_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> int:

        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        try:
            # -------------------------------------------------
            # 1. Resolve Security identity.
            # -------------------------------------------------
            security = self._get_security(symbol)

            # -------------------------------------------------
            # 2. Fetch external data.
            #
            # No database mutation has happened yet.
            # -------------------------------------------------
            raw_history = self.client.get_price_history(
                symbol,
                period=period,
            )

            # -------------------------------------------------
            # 3. Transform external data.
            # -------------------------------------------------
            prices = DataTransformer.prices(
                raw_history
            )

            # -------------------------------------------------
            # 4. Clean transformed data.
            # -------------------------------------------------
            prices = [
                DataCleaner.clean_price(price)
                for price in prices
            ]

            # -------------------------------------------------
            # 5. Validate the complete dataset BEFORE writing.
            # -------------------------------------------------
            if not DataValidator.validate_prices(
                prices
            ):
                raise ValueError(
                    f"Invalid price data for '{symbol}'."
                )

            inserted = 0

            # -------------------------------------------------
            # 6. Reconcile existing prices.
            # -------------------------------------------------
            for data in prices:

                existing = (
                    self.price_repo
                    .get_by_security_and_date(
                        security.id,
                        data.date,
                    )
                )

                if existing is not None:
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

            # -------------------------------------------------
            # 7. ONE transaction boundary.
            #
            # Nothing is committed until every price has been
            # successfully processed.
            # -------------------------------------------------
            self.db.commit()

            return inserted

        except Exception:
            # -------------------------------------------------
            # Any failure means the entire sync is rolled back.
            # -------------------------------------------------
            self.db.rollback()
            raise

    def get_price_history(
        self,
        symbol: str,
    ):
        security = self._get_security(symbol)

        return self.price_repo.get_for_security(
            security.id
        )