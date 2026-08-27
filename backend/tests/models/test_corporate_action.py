from datetime import date

from quantcore.core.enums import CorporateActionType
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
