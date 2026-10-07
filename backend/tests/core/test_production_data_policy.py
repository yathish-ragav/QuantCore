from unittest.mock import patch

import pytest

from quantcore.core.exceptions import ConfigurationError
from quantcore.core.production_data_policy import ProductionDataPolicy


def test_production_policy_allows_development_provider_configuration():
    with patch(
        "quantcore.core.production_data_policy.settings.ENVIRONMENT",
        "development",
    ):
        ProductionDataPolicy.validate_market_provider("yahoo")


def test_production_policy_requires_massive():
    with (  # noqa: SIM117
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
            "key",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_DATA_LICENSE_CONFIRMED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_DATA_LICENSE_REFERENCE",
            "contract:test",
        ),
    ):
        with pytest.raises(ConfigurationError, match=r"Massive"):
            ProductionDataPolicy.validate_market_provider("yahoo")


def test_production_policy_requires_massive_key():
    with (  # noqa: SIM117
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
            "",
        ),
    ):
        with pytest.raises(ConfigurationError, match=r"MASSIVE_API_KEY"):
            ProductionDataPolicy.validate_market_provider("massive")


def test_production_policy_accepts_documented_stack():
    with (
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
            "key",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_DATA_LICENSE_CONFIRMED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_DATA_LICENSE_REFERENCE",
            "contract:test",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.FRED_DATA_TERMS_CONFIRMED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.FRED_DATA_TERMS_REFERENCE",
            "terms:test",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.FRED_DATA_STORAGE_AUTHORIZED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.FRED_DATA_STORAGE_REFERENCE",
            "permission:test",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.SEC_DATA_POLICY_CONFIRMED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.SEC_DATA_POLICY_REFERENCE",
            "policy:test",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.market_data_provider",
            "massive",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.realtime_market_data_provider",
            "massive",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.financial_data_provider",
            "sec",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.regulatory_data_provider",
            "sec",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.macro_data_provider",
            "fred",
        ),
    ):
        ProductionDataPolicy.validate_all()


def test_production_policy_cannot_be_disabled_in_production():
    with (  # noqa: SIM117
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
            False,
        ),
    ):
        with pytest.raises(ConfigurationError, match=r"must\ be\ true"):
            ProductionDataPolicy.validate_all()


def test_provider_validation_is_enforced_when_flag_is_false():
    with (  # noqa: SIM117
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
            False,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
            "key",
        ),
    ):
        with pytest.raises(ConfigurationError, match=r"Massive"):
            ProductionDataPolicy.validate_market_provider("yahoo")


def test_production_policy_requires_massive_license_attestation():
    with (  # noqa: SIM117
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
            "key",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_DATA_LICENSE_CONFIRMED",
            False,
        ),
    ):
        with pytest.raises(ConfigurationError, match=r"attestation"):
            ProductionDataPolicy.validate_market_provider("massive")


def test_production_policy_requires_license_reference():
    with (  # noqa: SIM117
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
            "key",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_DATA_LICENSE_CONFIRMED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.MASSIVE_DATA_LICENSE_REFERENCE",
            "",
        ),
    ):
        with pytest.raises(ConfigurationError, match=r"reference"):
            ProductionDataPolicy.validate_market_provider("massive")


def test_production_policy_blocks_fred_persistence_without_storage_authorization():
    with (  # noqa: SIM117
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.FRED_DATA_STORAGE_AUTHORIZED",
            False,
        ),
    ):
        with pytest.raises(ConfigurationError, match=r"FRED\ storage"):
            ProductionDataPolicy.validate_macro_storage("fred")


def test_production_policy_requires_fred_storage_reference():
    with (  # noqa: SIM117
        patch(
            "quantcore.core.production_data_policy.settings.ENVIRONMENT",
            "production",
        ),
        patch(
            "quantcore.core.production_data_policy.settings.FRED_DATA_STORAGE_AUTHORIZED",
            True,
        ),
        patch(
            "quantcore.core.production_data_policy.settings.FRED_DATA_STORAGE_REFERENCE",
            "",
        ),
    ):
        with pytest.raises(ConfigurationError, match=r"reference"):
            ProductionDataPolicy.validate_macro_storage("fred")
