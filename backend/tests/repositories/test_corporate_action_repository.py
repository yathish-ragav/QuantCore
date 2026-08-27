from datetime import date
from unittest.mock import Mock

from quantcore.core.enums import CorporateActionType
from quantcore.models.corporate_action import CorporateAction
from quantcore.repositories.corporate_action_repository import (
    CorporateActionRepository,
)


def make_repository():
    db = Mock()
    return CorporateActionRepository(db), db


def test_get_for_security():
    repository, db = make_repository()
    actions = [Mock(spec=CorporateAction), Mock(spec=CorporateAction)]
    db.scalars.return_value.all.return_value = actions

    assert repository.get_for_security(1) == actions
    db.scalars.assert_called_once()


def test_get_by_identity():
    repository, db = make_repository()
    action = Mock(spec=CorporateAction)
    db.scalar.return_value = action

    result = repository.get_by_identity(
        1,
        date(2024, 8, 12),
        CorporateActionType.STOCK_SPLIT,
    )

    assert result is action
    db.scalar.assert_called_once()


def test_create():
    repository, db = make_repository()

    action = repository.create(
        security_id=1,
        effective_date=date(2024, 8, 12),
        action_type=CorporateActionType.STOCK_SPLIT,
        split_ratio=4.0,
    )

    db.add.assert_called_once_with(action)
    assert isinstance(action, CorporateAction)
    assert action.security_id == 1
    assert action.split_ratio == 4.0
    db.commit.assert_not_called()
