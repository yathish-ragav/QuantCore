from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ResearchFactorValueResponse(BaseModel):
    """Stable API projection of one deterministic PIT factor value."""

    factor_key: str
    definition_version: str
    symbol: str
    security_id: int
    as_of: datetime
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    input_manifest: dict[str, Any] | None
