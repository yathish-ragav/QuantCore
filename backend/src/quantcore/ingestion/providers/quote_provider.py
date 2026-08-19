from abc import ABC, abstractmethod

from quantcore.schemas.quote import QuoteData


class QuoteProvider(ABC):
    """Provider interface for current market quotes."""

    @abstractmethod
    def get_quote(self, symbol: str) -> QuoteData:
        raise NotImplementedError
