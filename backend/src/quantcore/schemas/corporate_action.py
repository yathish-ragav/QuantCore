from datetime import date

from pydantic import BaseModel, Field

from quantcore.core.enums import CorporateActionType


class CorporateActionData(BaseModel):
    """Normalized security-level corporate action."""

    effective_date: date
    action_type: CorporateActionType
    amount: float | None = Field(default=None, ge=0)
    split_ratio: float | None = Field(default=None, gt=0)
