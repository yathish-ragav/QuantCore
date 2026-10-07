from dataclasses import dataclass
from datetime import datetime, time, timezone

from sqlalchemy.orm import Session

from quantcore.core.exceptions import (
    DataValidationError,
    InvalidInputError,
    ResourceNotFoundError,
)
from quantcore.ingestion.providers.factory import ProviderFactory
from quantcore.models.price import Price
from quantcore.models.provenance import DataSource
from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.repositories.price_observation_revision_repository import (
    PriceObservationRevisionRepository,
)
from quantcore.repositories.price_repository import PriceRepository
from quantcore.repositories.security_repository import SecurityRepository
from quantcore.schemas.price import PriceData
from quantcore.services.security_listing_identity_service import (
    SecurityListingIdentityService,
)


@dataclass(frozen=True)
class PriceSyncResult:
    """Reconciliation counts and observed coverage from one market-price sync."""

    created: int
    updated: int
    unchanged: int
    records_processed: int
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None


class PriceService:

    def __init__(self, db: Session):
        self.db = db

        self.client = ProviderFactory.get_provider()

        self.security_repo = SecurityRepository(db)
        self.listing_identity_service = SecurityListingIdentityService(db)
        self.price_repo = PriceRepository(db)
        self.revision_repo = PriceObservationRevisionRepository(db)

    def get_security(
        self,
        symbol: str,
    ):
        symbol = DataCleaner.clean_symbol(symbol)

        if not symbol:
            raise InvalidInputError("Symbol must not be empty.")

        security = self.security_repo.get_by_symbol(symbol)

        if security is None:
            raise ResourceNotFoundError(
                f"Security '{symbol}' not found. " "Run security sync first."
            )

        return security

    @staticmethod
    def _matches(existing, data) -> bool:
        # Legacy rows may retain a provider-specific time component. Daily
        # identity is the calendar date; comparing the full timestamp would
        # create a spurious revision on every sync.
        if existing.date.date() != data.date.date():
            return False
        return all(
            getattr(existing, field) == getattr(data, field)
            for field in (
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "price_basis",
                "volume",
                "dividends",
                "stock_splits",
                "source_reference",
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
            raise InvalidInputError("Symbol must not be empty.")

        try:
            security = self.get_security(symbol)

            raw_history = self.client.get_price_history(
                symbol,
                period=period,
            )

            prices = DataTransformer.prices(raw_history)

            normalized_prices: list[PriceData] = []
            for price_data in prices:
                cleaned = DataCleaner.clean_price(price_data)
                normalized_prices.append(
                    cleaned.model_copy(
                        update={
                            # Daily bars are identified by the provider's
                            # calendar date, not by its timestamp. Persist a
                            # stable, timezone-naive midnight value.
                            "date": datetime.combine(
                                cleaned.date.date(),
                                time.min,
                            )
                        }
                    )
                )
            prices = normalized_prices

            if not DataValidator.validate_prices(prices):
                raise DataValidationError(f"Invalid price data for '{symbol}'.")

            created = 0
            updated = 0
            unchanged = 0
            records_processed = len(prices)
            source = DataSource(self.client.SOURCE)
            known_at = datetime.now(timezone.utc)
            for price in prices:
                price.source_reference = (
                    f"{source.value}:PRICE:DAY:{symbol}:"
                    f"{price.date.date().isoformat()}"
                )
            coverage_start = min((price.date for price in prices), default=None)
            coverage_end = max((price.date for price in prices), default=None)

            # Load all existing observations in one query. This avoids an N+1
            # SELECT pattern when backfilling years of daily history.
            existing_prices = self.price_repo.get_for_security_and_dates(
                security.id,
                [price.date for price in prices],
            )
            existing_by_date: dict[object, Price] = {}
            for existing in existing_prices:
                observation_day = existing.date.date()
                if observation_day in existing_by_date:
                    raise DataValidationError(
                        f"Multiple stored daily price observations for "
                        f"'{symbol}' on {observation_day.isoformat()}; "
                        "reconcile legacy duplicates before syncing."
                    )
                existing_by_date[observation_day] = existing

            new_prices: list[Price] = []
            changed_prices: list[Price] = []

            for price_data in prices:
                existing_price = existing_by_date.get(price_data.date.date())

                if existing_price is None:
                    created_price = self.price_repo.create(
                        security_id=security.id,
                        date=price_data.date,
                        open=price_data.open,
                        high=price_data.high,
                        low=price_data.low,
                        close=price_data.close,
                        adjusted_close=price_data.adjusted_close,
                        price_basis=price_data.price_basis,
                        volume=price_data.volume,
                        dividends=price_data.dividends,
                        stock_splits=price_data.stock_splits,
                        source=source,
                        fetched_at=known_at,
                        source_reference=price_data.source_reference,
                    )
                    new_prices.append(created_price)
                    created += 1
                    continue

                if self._matches(existing_price, price_data):
                    unchanged += 1
                    continue

                existing_price.open = price_data.open
                existing_price.high = price_data.high
                existing_price.low = price_data.low
                existing_price.close = price_data.close
                existing_price.adjusted_close = price_data.adjusted_close
                existing_price.price_basis = price_data.price_basis
                existing_price.volume = price_data.volume
                existing_price.dividends = price_data.dividends
                existing_price.stock_splits = price_data.stock_splits
                existing_price.source = source
                existing_price.fetched_at = known_at
                existing_price.source_reference = price_data.source_reference
                changed_prices.append(existing_price)
                updated += 1

            # New rows need database-generated IDs before their immutable
            # revision snapshots can be created. One flush is sufficient for
            # the entire batch.
            if new_prices:
                self.db.flush()

            next_revision_numbers = self.revision_repo.get_next_revision_numbers(
                [changed_price.id for changed_price in changed_prices]
            )

            for new_price in new_prices:
                self._create_revision(
                    new_price,
                    source=source,
                    known_at=known_at,
                    revision_number=1,
                )

            for changed_price in changed_prices:
                self._create_revision(
                    changed_price,
                    source=source,
                    known_at=known_at,
                    revision_number=next_revision_numbers[changed_price.id],
                )

            self.db.commit()

            return PriceSyncResult(
                created=created,
                updated=updated,
                unchanged=unchanged,
                records_processed=records_processed,
                coverage_start=coverage_start,
                coverage_end=coverage_end,
            )

        except Exception:
            self.db.rollback()
            raise

    def get_price_history(
        self,
        symbol: str,
    ):
        security = self.get_security(symbol)

        return self.price_repo.get_for_security(security.id)

    def get_price_revision_history_known_as_of(
        self,
        symbol: str,
        as_of: datetime,
    ):
        """Return all price revisions known by ``as_of`` for PIT backtest valuation."""
        if not isinstance(as_of, datetime):
            raise InvalidInputError("Price revision as_of must be a datetime.")
        security = self.listing_identity_service.resolve_security_as_of(
            symbol,
            as_of=as_of,
        )

        return self.revision_repo.get_revisions_for_security_known_as_of(
            security.id,
            as_of,
        )

    def get_price_history_as_of(
        self,
        symbol: str,
        as_of: datetime,
    ):
        security = self.listing_identity_service.resolve_security_as_of(
            symbol,
            as_of=as_of,
        )

        return self.revision_repo.get_latest_for_security_as_of(
            security.id,
            as_of,
        )
