from quantcore.schemas.company import CompanyData
from quantcore.schemas.income_statement import IncomeStatementData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData


class DataTransformer:

    @staticmethod
    def company(data) -> CompanyData:
        if isinstance(data, CompanyData):
            return data

        if isinstance(data, dict):
            return CompanyData.model_validate(data)

        raise TypeError(
            "Company data must be a CompanyData instance "
            "or dictionary."
        )

    @staticmethod
    def price(data) -> PriceData:
        if isinstance(data, PriceData):
            return data

        if isinstance(data, dict):
            return PriceData.model_validate(data)

        raise TypeError(
            "Price data must be a PriceData instance "
            "or dictionary."
        )

    @staticmethod
    def news(data) -> NewsData:
        if isinstance(data, NewsData):
            return data

        if isinstance(data, dict):
            return NewsData.model_validate(data)

        raise TypeError(
            "News data must be a NewsData instance "
            "or dictionary."
        )

    @staticmethod
    def income_statement(
        data,
    ) -> IncomeStatementData:

        if isinstance(data, IncomeStatementData):
            return data

        if isinstance(data, dict):
            return IncomeStatementData.model_validate(
                data
            )

        raise TypeError(
            "Income statement data must be an "
            "IncomeStatementData instance or dictionary."
        )

    @staticmethod
    def companies(
        data,
    ) -> list[CompanyData]:

        if not isinstance(data, list):
            raise TypeError(
                "Company data must be a list."
            )

        return [
            DataTransformer.company(item)
            for item in data
        ]

    @staticmethod
    def prices(
        data,
    ) -> list[PriceData]:

        if not isinstance(data, list):
            raise TypeError(
                "Price data must be a list."
            )

        return [
            DataTransformer.price(item)
            for item in data
        ]

    @staticmethod
    def news_articles(
        data,
    ) -> list[NewsData]:

        if not isinstance(data, list):
            raise TypeError(
                "News data must be a list."
            )

        return [
            DataTransformer.news(item)
            for item in data
        ]

    @staticmethod
    def income_statements(
        data,
    ) -> list[IncomeStatementData]:

        if not isinstance(data, list):
            raise TypeError(
                "Income statement data must be a list."
            )

        return [
            DataTransformer.income_statement(item)
            for item in data
        ]