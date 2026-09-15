from datetime import date, datetime, timezone

from quantcore.core.security_identity import SecurityIdentifierType
from quantcore.models.security_identifier import SecurityIdentifier


def test_security_identifier_model_has_pit_fields():
    identifier = SecurityIdentifier(
        security_id=1,
        identifier_type=SecurityIdentifierType.ISIN,
        namespace="ISIN",
        value="US0378331005",
        valid_from=date(2020, 1, 1),
        known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
        source="SEC",
    )

    assert identifier.security_id == 1
    assert identifier.identifier_type is SecurityIdentifierType.ISIN
    assert identifier.namespace == "ISIN"
    assert identifier.value == "US0378331005"
    assert identifier.valid_to is None
