from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import DataValidationError
from quantcore.models.market_index_source import (
    IndexLicenseStatus,
    IndexSourceAuthority,
)
from quantcore.services.market_index_source_service import MarketIndexDataSourceService


def make_service():
    service = MarketIndexDataSourceService.__new__(MarketIndexDataSourceService)
    service.db = Mock()
    service.repository = Mock()
    return service


def test_create_normalizes_key_and_defaults_to_not_reviewed():
    service = make_service()
    service.repository.get_by_key.return_value = None
    source = Mock()
    source.key = "NASDAQ_GIW"
    service.repository.create.return_value = source

    result = service.create(
        key=" nasdaq_giw ",
        provider="Nasdaq",
        dataset="Global Index Watch",
        authority=IndexSourceAuthority.AUTHORITATIVE,
    )

    assert result is source
    service.repository.create.assert_called_once()
    assert (
        service.repository.create.call_args.kwargs["license_status"]
        == IndexLicenseStatus.NOT_REVIEWED.value
    )
    service.db.flush.assert_called_once()


def test_require_storage_authorized_rejects_unlicensed_source():
    service = make_service()
    source = Mock()
    source.key = "NASDAQ_GIW"
    source.license_status = IndexLicenseStatus.PENDING
    source.storage_allowed = True
    source.reviewed_at = datetime.now(timezone.utc)
    source.license_reference = "contract:test"
    source.terms_reference = None
    source.expires_at = None
    service.repository.get_by_key.return_value = source

    with pytest.raises(DataValidationError, match="not authorized"):
        service.require_storage_authorized("NASDAQ_GIW")


def test_require_storage_authorized_rejects_expired_authorization():
    service = make_service()
    source = Mock()
    source.key = "NASDAQ_GIW"
    source.license_status = IndexLicenseStatus.AUTHORIZED
    source.storage_allowed = True
    source.reviewed_at = datetime.now(timezone.utc)
    source.license_reference = "contract:test"
    source.terms_reference = None
    source.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    service.repository.get_by_key.return_value = source

    with pytest.raises(DataValidationError, match="expired"):
        service.require_storage_authorized("NASDAQ_GIW")


def test_require_storage_authorized_requires_documented_review():
    service = make_service()
    source = Mock()
    source.key = "SPDJI"
    source.license_status = IndexLicenseStatus.AUTHORIZED
    source.storage_allowed = True
    source.reviewed_at = None
    source.license_reference = "contract:test"
    source.terms_reference = None
    source.expires_at = None
    service.repository.get_by_key.return_value = source

    with pytest.raises(DataValidationError, match="licensing review"):
        service.require_storage_authorized("SPDJI")


def test_require_storage_authorized_requires_terms_or_license_reference():
    service = make_service()
    source = Mock()
    source.key = "SPDJI"
    source.license_status = IndexLicenseStatus.AUTHORIZED
    source.storage_allowed = True
    source.reviewed_at = datetime.now(timezone.utc)
    source.license_reference = None
    source.terms_reference = None
    source.expires_at = None
    service.repository.get_by_key.return_value = source

    with pytest.raises(DataValidationError, match="reference"):
        service.require_storage_authorized("SPDJI")


def test_require_display_authorized_rejects_when_display_not_allowed():
    service = make_service()
    source = Mock()
    source.key = "NASDAQ_GIW"
    source.license_status = IndexLicenseStatus.AUTHORIZED
    source.display_allowed = False
    source.reviewed_at = datetime.now(timezone.utc)
    source.license_reference = "contract:test"
    source.terms_reference = None
    source.expires_at = None
    service.repository.get_by_key.return_value = source

    with pytest.raises(DataValidationError, match="does not permit display"):
        service.require_display_authorized("NASDAQ_GIW")


def test_require_display_authorized_accepts_valid_current_authorization():
    service = make_service()
    source = Mock()
    source.key = "NASDAQ_GIW"
    source.id = 7
    source.license_status = IndexLicenseStatus.AUTHORIZED
    source.display_allowed = True
    source.reviewed_at = datetime.now(timezone.utc)
    source.license_reference = "contract:test"
    source.terms_reference = None
    source.expires_at = None
    service.repository.get_by_key.return_value = source

    assert service.require_display_authorized("NASDAQ_GIW") is source
