from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def isolate_production_data_policy_from_local_environment():
    """Keep the test suite deterministic when a developer has a production .env."""
    with patch("quantcore.core.production_data_policy.settings.ENVIRONMENT", "test"), patch(
        "quantcore.core.production_data_policy.settings.PRODUCTION_DATA_POLICY_ENFORCED",
        False,
    ):
        yield
