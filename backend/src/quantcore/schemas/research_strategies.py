from pydantic import BaseModel, Field

from quantcore.services.research_strategy_service import ResearchStrategyDirection


class ResearchStrategyRequest(BaseModel):
    """Declarative versioned strategy definition submitted through the API."""

    strategy_key: str = Field(min_length=1, max_length=100)
    definition_version: str = Field(min_length=1, max_length=100)
    signal_identity: tuple[str, str]
    direction: ResearchStrategyDirection
    long_threshold: float | None = None
    short_threshold: float | None = None
    description: str | None = Field(default=None, max_length=500)


class ResearchStrategyResponse(BaseModel):
    """Stable API projection of a validated research strategy definition."""

    strategy_key: str
    definition_version: str
    signal_identity: tuple[str, str]
    direction: ResearchStrategyDirection
    long_threshold: float | None
    short_threshold: float | None
    description: str | None
