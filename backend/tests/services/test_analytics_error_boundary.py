from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError, ResourceNotFoundError
from quantcore.services.analytics_service import AnalyticsService


def make_service():
    service = AnalyticsService.__new__(AnalyticsService)
    service.security_repo = Mock()
    service.price_repo = Mock()
    return service


def test_analytics_empty_symbol_is_invalid():
    service = make_service()

    with pytest.raises(InvalidInputError):
        service._get_prices("")


def test_analytics_unknown_symbol_is_not_found():
    service = make_service()
    service.security_repo.get_by_symbol.return_value = None

    with pytest.raises(
        ResourceNotFoundError,
        match="Security 'AAPL' not found\\.",
    ):
        service._get_prices("AAPL")

    service.price_repo.get_for_security.assert_not_called()
