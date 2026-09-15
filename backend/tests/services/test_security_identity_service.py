from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import DataValidationError
from quantcore.core.security_identity import SecurityIdentifierType
from quantcore.services.security_identity_service import (
    SecurityIdentifierInput,
    SecurityIdentityService,
)


def make_service():
    db = Mock()
    service = SecurityIdentityService.__new__(SecurityIdentityService)
    service.db = db
    service.repository = Mock()
    service.security_repository = Mock()
    return service, db


def test_record_identifier_normalizes_value_and_source():
    service, db = make_service()
    security = Mock(id=10)
    db.get.return_value = security
    service.repository.get_exact.return_value = None
    service.repository.get_for_security.return_value = []
    service.repository.resolve_as_of.return_value = None
    created = Mock()
    service.repository.create.return_value = created

    result = service.record_identifier(
        SecurityIdentifierInput(
            security_id=10,
            identifier_type=SecurityIdentifierType.ISIN,
            value=" us0378331005 ",
            valid_from=date(2020, 1, 1),
            valid_to=None,
            known_at=datetime(2020, 1, 2),
            source=" sec ",
        )
    )

    assert result is created
    kwargs = service.repository.create.call_args.kwargs
    assert kwargs["value"] == "US0378331005"
    assert kwargs["source"] == "SEC"
    db.flush.assert_called_once()


def test_record_identifier_rejects_same_value_for_another_security():
    service, db = make_service()
    db.get.return_value = Mock(id=10)
    service.repository.get_exact.return_value = None
    service.repository.get_for_security.return_value = []
    service.repository.resolve_as_of.return_value = Mock(security_id=99)

    with pytest.raises(DataValidationError, match="already mapped"):
        service.record_identifier(
            SecurityIdentifierInput(
                security_id=10,
                identifier_type=SecurityIdentifierType.ISIN,
                value="US0378331005",
                valid_from=date(2020, 1, 1),
                valid_to=None,
                known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
                source="SEC",
            )
        )
