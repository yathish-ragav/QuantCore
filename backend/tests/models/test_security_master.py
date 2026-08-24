from datetime import datetime, timezone

from quantcore.models.security import Security, SecurityStatus
from quantcore.models.security_identifier_history import SecurityIdentifierHistory


def test_security_identity_is_company_symbol_exchange():
    constraint_names = {
        constraint.name
        for constraint in Security.__table__.constraints
        if constraint.name
    }
    assert "uq_security_company_symbol_exchange" in constraint_names
    assert "uq_security_symbol" not in constraint_names


def test_security_has_lifecycle_fields():
    columns = Security.__table__.columns
    assert "status" in columns
    assert "first_seen_at" in columns
    assert "last_seen_at" in columns


def test_identifier_history_has_temporal_identity():
    columns = SecurityIdentifierHistory.__table__.columns
    assert {"security_id", "symbol", "exchange", "first_seen_at", "last_seen_at", "is_current"} <= set(columns.keys())


def test_security_status_can_be_assigned():
    now = datetime.now(timezone.utc)
    security = Security(
        company_id=1,
        symbol="AAPL",
        exchange="NASDAQ",
        status=SecurityStatus.ACTIVE,
        first_seen_at=now,
        last_seen_at=now,
    )
    assert security.status == SecurityStatus.ACTIVE
