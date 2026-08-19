from quantcore.core.exceptions import InvalidInputError
from quantcore.ingestion.providers.quote_factory import QuoteProviderFactory
from quantcore.schemas.quote import QuoteData


class QuoteService:
    """Application service for current market quotes."""

    def __init__(self) -> None:
        self.provider = QuoteProviderFactory.get_provider()

    def get_quote(self, symbol: str) -> QuoteData:
        symbol = symbol.strip().upper()

        if not symbol:
            raise InvalidInputError(
                "Symbol must not be empty."
            )

        return self.provider.get_quote(symbol)
