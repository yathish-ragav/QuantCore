from abc import ABC, abstractmethod
from typing import ClassVar

from quantcore.schemas.company import CompanyData
from quantcore.schemas.corporate_action import CorporateActionData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData


class MarketDataProvider(ABC):
    SOURCE: ClassVar[str]
    """
    Base interface for all market data providers.
    """

    @abstractmethod
    def get_company_info(
        self,
        symbol: str,
    ) -> CompanyData:
        """
        Return company profile.
        """
        ...

    @abstractmethod
    def get_price_history(
        self,
        symbol: str,
        period: str = "5y",
    ) -> list[PriceData]:
        """
        Return historical price data.
        """
        ...

    @abstractmethod
    def get_corporate_actions(
        self,
        symbol: str,
        period: str = "max",
    ) -> list[CorporateActionData]:
        """
        Return normalized historical corporate actions.
        """
        ...

    @abstractmethod
    def get_news(
        self,
        symbol: str,
    ) -> list[NewsData]:
        """
        Return latest news articles.
        """
