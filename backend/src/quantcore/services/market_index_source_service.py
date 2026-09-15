from datetime import datetime, timezone

from quantcore.core.exceptions import DataValidationError, InvalidInputError, ResourceNotFoundError
from quantcore.models.market_index_source import (
    IndexLicenseStatus,
    IndexSourceAuthority,
    MarketIndexDataSource,
)
from quantcore.repositories.market_index_source_repository import MarketIndexDataSourceRepository


class MarketIndexDataSourceService:
    """Manage index-source metadata and the operational licensing gate."""

    def __init__(self, db):
        self.db = db
        self.repository = MarketIndexDataSourceRepository(db)

    @staticmethod
    def _key(value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise InvalidInputError("Index data-source key must not be empty.")
        return value

    def get(self, key: str) -> MarketIndexDataSource:
        source = self.repository.get_by_key(self._key(key))
        if source is None:
            raise ResourceNotFoundError(f"Index data source '{key}' not found.")
        return source

    def create(
        self,
        *,
        key: str,
        provider: str,
        dataset: str,
        authority: IndexSourceAuthority,
        license_status: IndexLicenseStatus = IndexLicenseStatus.NOT_REVIEWED,
        storage_allowed: bool = False,
        display_allowed: bool = False,
        redistribution_allowed: bool = False,
        terms_reference: str | None = None,
        license_reference: str | None = None,
        attribution_text: str | None = None,
        reviewed_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> MarketIndexDataSource:
        key = self._key(key)
        if not provider.strip() or not dataset.strip():
            raise InvalidInputError("Provider and dataset are required.")
        if self.repository.get_by_key(key) is not None:
            raise DataValidationError(f"Index data source '{key}' already exists.")
        source = self.repository.create(
            key=key,
            provider=provider.strip(),
            dataset=dataset.strip(),
            authority=authority.value,
            license_status=license_status.value,
            storage_allowed=storage_allowed,
            display_allowed=display_allowed,
            redistribution_allowed=redistribution_allowed,
            terms_reference=terms_reference,
            license_reference=license_reference,
            attribution_text=attribution_text,
            reviewed_at=reviewed_at,
            expires_at=expires_at,
        )
        self.db.flush()
        return source

    def require_storage_authorized(self, key: str) -> MarketIndexDataSource:
        source = self.get(key)
        now = datetime.now(timezone.utc)
        try:
            license_status = IndexLicenseStatus(source.license_status)
        except ValueError as exc:
            raise DataValidationError(
                f"Index data source '{source.key}' has an unsupported license status."
            ) from exc
        if license_status is not IndexLicenseStatus.AUTHORIZED:
            raise DataValidationError(
                f"Index data source '{source.key}' is not authorized for persistence."
            )
        if not source.storage_allowed:
            raise DataValidationError(
                f"Index data source '{source.key}' does not permit persistent storage."
            )
        if source.expires_at is not None:
            expires_at = source.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                raise DataValidationError(
                    f"Index data source '{source.key}' authorization has expired."
                )
        return source
