from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import (
    DataValidationError,
    InvalidInputError,
    ResourceNotFoundError,
)
from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.models.provenance import DataSource
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.price_observation_revision_repository import (
    PriceObservationRevisionRepository,
)
from quantcore.repositories.price_repository import PriceRepository
from quantcore.repositories.security_repository import SecurityRepository


@dataclass(frozen=True)
class PriceSyncResult:
    """Reconciliation counts produced by one market-price sync."""

    created: int
    updated: int
    unchanged: int
    records_processed: int


class PriceService:

    def __init__(self, db: Session):
        self.db = db

        self.client = ProviderFactory.get_provider()

        self.security_repo = SecurityRepository(db)
        self.price_repo = PriceRepository(db)
        self.revision_repo = PriceObservationRevisionRepository(db)

    def get_security(
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
                "Run security sync first."
            )

        return security

    @staticmethod
    def _matches(existing, data) -> bool:
        return all(
            getattr(existing, field) == getattr(data, field)
            for field in (
                "date",
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "price_basis",
                "volume",
                "dividends",
                "stock_splits",
            )
        )

    def _create_revision(
        self,
        price,
        *,
        source: DataSource,
        known_at: datetime,
        revision_number: int,
    ):
        self.revision_repo.create(
            price_id=price.id,
            revision_number=revision_number,
            date=price.date,
            open=price.open,
            high=price.high,
            low=price.low,
            close=price.close,
            adjusted_close=price.adjusted_close,
            price_basis=price.price_basis,
            volume=price.volume,
            dividends=price.dividends,
            stock_splits=price.stock_splits,
            source=source,
            known_at=known_at,
            source_reference=price.source_reference,
        )

    def sync_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> PriceSyncResult:

        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        try:
            security = self.get_security(symbol)

            raw_history = self.client.get_price_history(
                symbol,
                period=period,
            )

            prices = DataTransformer.prices(
                raw_history
            )

            prices = [
                DataCleaner.clean_price(price)
                for price in prices
            ]

            if not DataValidator.validate_prices(
                prices
            ):
                raise DataValidationError(
                    f"Invalid price data for '{symbol}'."
                )

            created = 0
            updated = 0
            unchanged = 0
            records_processed = 0
            source = DataSource(self.client.SOURCE)
            known_at = datetime.now(timezone.utc)

            for data in prices:
                records_processed += 1
                existing = self.price_repo.get_by_security_and_date(
                    security.id,
                    data.date,
                )

                if existing is None:
                    price = self.price_repo.create(
                        security_id=security.id,
                        date=data.date,
                        open=data.open,
                        high=data.high,
                        low=data.low,
                        close=data.close,
                        adjusted_close=data.adjusted_close,
                        price_basis=data.price_basis,
                        volume=data.volume,
                        dividends=data.dividends,
                        stock_splits=data.stock_splits,
                        source=source,
                        fetched_at=known_at,
                    )
                    self.db.flush()
                    self._create_revision(
                        price,
                        source=source,
                        known_at=known_at,
                        revision_number=1,
                    )
                    created += 1
                    continue

                if self._matches(existing, data):
                    unchanged += 1
                    continue

                next_revision = self.revision_repo.get_next_revision_number(
                    existing.id
                )

                existing.open = data.open
                existing.high = data.high
                existing.low = data.low
                existing.close = data.close
                existing.adjusted_close = data.adjusted_close
                existing.price_basis = data.price_basis
                existing.volume = data.volume
                existing.dividends = data.dividends
                existing.stock_splits = data.stock_splits
                existing.source = source
                existing.fetched_at = known_at

                self._create_revision(
                    existing,
                    source=source,
                    known_at=known_at,
                    revision_number=next_revision,
                )
                updated += 1

            self.db.commit()

            return PriceSyncResult(
                created=created,
                updated=updated,
                unchanged=unchanged,
                records_processed=records_processed,
            )

        except Exception:
            self.db.rollback()
            raise

    def get_price_history(
        self,
        symbol: str,
    ):
        security = self.get_security(symbol)

        return self.price_repo.get_for_security(
            security.id
        )

    def get_price_history_as_of(
        self,
        symbol: str,
        as_of: datetime,
    ):
        security = self.get_security(symbol)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        return self.revision_repo.get_latest_for_security_as_of(
            security.id,
            as_of,
        )
