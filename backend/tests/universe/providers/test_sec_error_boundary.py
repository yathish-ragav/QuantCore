from unittest.mock import Mock, patch

import pytest
import requests

from quantcore.core.exceptions import DataValidationError, ExternalDataError
from quantcore.universe.providers.sec import SECUniverseProvider


def test_sec_universe_http_error_is_external_data_error():
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("500")

    with patch(
        "quantcore.universe.providers.sec.requests.get",
        return_value=response,
    ):
        with pytest.raises(ExternalDataError):
            SECUniverseProvider().fetch()


def test_sec_universe_invalid_shape_is_data_validation_error():
    response = Mock()
    response.json.return_value = []

    with patch(
        "quantcore.universe.providers.sec.requests.get",
        return_value=response,
    ):
        with pytest.raises(DataValidationError):
            SECUniverseProvider().fetch()
