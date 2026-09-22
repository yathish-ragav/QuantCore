from datetime import date

from quantcore.core.enums import CorporateActionType
from quantcore.models.provenance import DataSource
from quantcore.models.corporate_action import CorporateAction


def test_corporate_action_model():
    action = CorporateAction(
        security_id=1,
        effective_date=date(2024, 8, 12),
        action_type=CorporateActionType.STOCK_SPLIT,
        split_ratio=4.0,
    )

    assert action.security_id == 1
    assert action.effective_date == date(2024, 8, 12)
    assert action.action_type is CorporateActionType.STOCK_SPLIT
    assert action.split_ratio == 4.0
    assert action.amount is None
    assert action.related_security_id is None


def test_corporate_action_supports_identity_impacting_fields():
    action = CorporateAction(
        security_id=1,
        effective_date=date(2025, 1, 1),
        action_type=CorporateActionType.TICKER_CHANGE,
        old_symbol="OLD",
        new_symbol="NEW",
        old_exchange="NYSE",
        new_exchange="NASDAQ",
        related_security_id=2,
    )

    assert action.action_type is CorporateActionType.TICKER_CHANGE
    assert action.old_symbol == "OLD"
    assert action.new_symbol == "NEW"
    assert action.old_exchange == "NYSE"
    assert action.new_exchange == "NASDAQ"
    assert action.related_security_id == 2


def test_corporate_action_provider_identity_allows_same_date_with_distinct_reference():
    first = CorporateAction(
        security_id=1,
        effective_date=date(2012, 11, 29),
        action_type=CorporateActionType.DIVIDEND,
        amount=0.12,
        source=DataSource.MASSIVE,
        source_reference="MASSIVE:DIVIDEND:regular",
    )
    second = CorporateAction(
        security_id=1,
        effective_date=date(2012, 11, 29),
        action_type=CorporateActionType.DIVIDEND,
        amount=0.12,
        source=DataSource.MASSIVE,
        source_reference="MASSIVE:DIVIDEND:special",
    )

    assert first.source_reference != second.source_reference
