from datetime import date, datetime, timezone

from quantcore.core.enums import CorporateActionType
from quantcore.models.corporate_action_revision import CorporateActionRevision


def test_corporate_action_revision_model():
    known_at = datetime(2026, 8, 28, tzinfo=timezone.utc)
    revision = CorporateActionRevision(
        action_id=7,
        security_id=1,
        revision_number=1,
        effective_date=date(2024, 8, 12),
        action_type=CorporateActionType.STOCK_SPLIT,
        split_ratio=4.0,
        known_at=known_at,
    )

    assert revision.action_id == 7
    assert revision.security_id == 1
    assert revision.revision_number == 1
    assert revision.effective_date == date(2024, 8, 12)
    assert revision.action_type is CorporateActionType.STOCK_SPLIT
    assert revision.split_ratio == 4.0
    assert revision.known_at == known_at


def test_revision_preserves_identity_impacting_fields():
    known_at = datetime(2026, 8, 28, tzinfo=timezone.utc)
    revision = CorporateActionRevision(
        action_id=7,
        security_id=1,
        revision_number=2,
        effective_date=date(2025, 1, 1),
        action_type=CorporateActionType.TICKER_CHANGE,
        related_security_id=2,
        old_symbol="OLD",
        new_symbol="NEW",
        known_at=known_at,
    )

    assert revision.related_security_id == 2
    assert revision.old_symbol == "OLD"
    assert revision.new_symbol == "NEW"
