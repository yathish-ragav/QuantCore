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
    with patch(
        "quantcore.core.production_data_policy.settings.ENVIRONMENT",
        "production",
    ), patch(
        "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
        True,
    ), patch(
        "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
        "key",
    ):
        with pytest.raises(ConfigurationError, match="Massive"):
            ProductionDataPolicy.validate_market_provider("yahoo")


def test_production_policy_requires_massive_key():
    with patch(
        "quantcore.core.production_data_policy.settings.ENVIRONMENT",
        "production",
    ), patch(
        "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
        True,
    ), patch(
        "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
        "",
    ):
        with pytest.raises(ConfigurationError, match="MASSIVE_API_KEY"):
            ProductionDataPolicy.validate_market_provider("massive")


def test_production_policy_accepts_documented_stack():
    with patch(
        "quantcore.core.production_data_policy.settings.ENVIRONMENT",
        "production",
    ), patch(
        "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
        True,
    ), patch(
        "quantcore.core.production_data_policy.settings.MASSIVE_API_KEY",
        "key",
    ), patch(
        "quantcore.core.production_data_policy.settings.market_data_provider",
        "massive",
    ), patch(
        "quantcore.core.production_data_policy.settings.realtime_market_data_provider",
        "massive",
    ), patch(
        "quantcore.core.production_data_policy.settings.financial_data_provider",
        "sec",
    ), patch(
        "quantcore.core.production_data_policy.settings.regulatory_data_provider",
        "sec",
    ), patch(
        "quantcore.core.production_data_policy.settings.macro_data_provider",
        "fred",
    ):
        ProductionDataPolicy.validate_all()
