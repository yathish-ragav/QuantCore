from __future__ import annotations

import re

from quantcore.schemas.balance_sheet import BalanceSheetData
from quantcore.schemas.cash_flow_statement import CashFlowStatementData
from quantcore.schemas.company import CompanyData
from quantcore.schemas.income_statement import IncomeStatementData
from quantcore.schemas.news import NewsData
from quantcore.schemas.price import PriceData


class DataCleaner:
    """
    Normalizes provider data before validation and transformation.

    The cleaner does not decide whether data is valid.
    It only removes formatting inconsistencies.
    """

    @staticmethod
    def clean_symbol(symbol: str) -> str:
        if not isinstance(symbol, str):
            raise TypeError("Symbol must be a string.")

        return symbol.strip().upper()

    @staticmethod
    def clean_text(value: str | None) -> str:
        if value is None:
            return ""

        if not isinstance(value, str):
            raise TypeError(
                "Text value must be a string or None."
            )

        return re.sub(
            r"\s+",
            " ",
            value.strip(),
        )

    @classmethod
    def clean_company(
        cls,
        data: CompanyData,
    ) -> CompanyData:

        return CompanyData(
            symbol=cls.clean_symbol(data.symbol),
            name=cls.clean_text(data.name),
            sector=cls.clean_text(data.sector),
            industry=cls.clean_text(data.industry),
            country=cls.clean_text(data.country),
            website=cls.clean_text(data.website),
            market_cap=data.market_cap,
        )

    @classmethod
    def clean_news(
        cls,
        data: NewsData,
    ) -> NewsData:

        return NewsData(
            title=cls.clean_text(data.title),
            publisher=cls.clean_text(data.publisher),
            summary=cls.clean_text(data.summary),
            url=cls.clean_text(data.url),
            published_at=data.published_at,
        )

    @staticmethod
    def clean_price(
        data: PriceData,
    ) -> PriceData:

        return PriceData(
            date=data.date,
            open=float(data.open),
            high=float(data.high),
            low=float(data.low),
            close=float(data.close),
            volume=int(data.volume),
            dividends=float(data.dividends),
            stock_splits=float(data.stock_splits),
        )

    @staticmethod
    def clean_income_statement(
        data: IncomeStatementData,
    ) -> IncomeStatementData:

        return IncomeStatementData(
            period_start=data.period_start,
            fiscal_year=data.fiscal_year,
            fiscal_period=data.fiscal_period,
            period_type=data.period_type,
            filing_date=data.filing_date,
            filing_form=data.filing_form,
            accession_number=data.accession_number,
            fiscal_date=data.fiscal_date,
            total_revenue=(
                float(data.total_revenue)
                if data.total_revenue is not None
                else None
            ),
            gross_profit=(
                float(data.gross_profit)
                if data.gross_profit is not None
                else None
            ),
            operating_income=(
                float(data.operating_income)
                if data.operating_income is not None
                else None
            ),
            net_income=(
                float(data.net_income)
                if data.net_income is not None
                else None
            ),
            eps=(
                float(data.eps)
                if data.eps is not None
                else None
            ),
            shares_outstanding=(
                int(data.shares_outstanding)
                if data.shares_outstanding is not None
                else None
            ),
        )


    @staticmethod
    def clean_balance_sheet(
        data: BalanceSheetData,
    ) -> BalanceSheetData:

        def _to_float(value):
            return float(value) if value is not None else None

        return BalanceSheetData(
            period_start=data.period_start,
            fiscal_year=data.fiscal_year,
            fiscal_period=data.fiscal_period,
            period_type=data.period_type,
            filing_date=data.filing_date,
            filing_form=data.filing_form,
            accession_number=data.accession_number,
            fiscal_date=data.fiscal_date,
            cash_and_cash_equivalents=_to_float(
                data.cash_and_cash_equivalents
            ),
            short_term_investments=_to_float(
                data.short_term_investments
            ),
            accounts_receivable=_to_float(
                data.accounts_receivable
            ),
            inventory=_to_float(data.inventory),
            total_current_assets=_to_float(
                data.total_current_assets
            ),
            property_plant_equipment_net=_to_float(
                data.property_plant_equipment_net
            ),
            goodwill=_to_float(data.goodwill),
            intangible_assets=_to_float(
                data.intangible_assets
            ),
            total_assets=_to_float(data.total_assets),
            accounts_payable=_to_float(data.accounts_payable),
            short_term_debt=_to_float(data.short_term_debt),
            total_current_liabilities=_to_float(
                data.total_current_liabilities
            ),
            long_term_debt=_to_float(data.long_term_debt),
            total_liabilities=_to_float(
                data.total_liabilities
            ),
            total_equity=_to_float(data.total_equity),
            retained_earnings=_to_float(
                data.retained_earnings
            ),
            total_debt=_to_float(data.total_debt),
            net_debt=_to_float(data.net_debt),
            working_capital=_to_float(
                data.working_capital
            ),
        )

    @staticmethod
    def clean_cash_flow_statement(
        data: CashFlowStatementData,
    ) -> CashFlowStatementData:

        def _to_float(value):
            return (
                float(value)
                if value is not None
                else None
            )

        return CashFlowStatementData(
            period_start=data.period_start,
            fiscal_year=data.fiscal_year,
            fiscal_period=data.fiscal_period,
            period_type=data.period_type,
            filing_date=data.filing_date,
            filing_form=data.filing_form,
            accession_number=data.accession_number,
            fiscal_date=data.fiscal_date,
            operating_cash_flow=_to_float(
                data.operating_cash_flow
            ),
            capital_expenditure=_to_float(
                data.capital_expenditure
            ),
            free_cash_flow=_to_float(
                data.free_cash_flow
            ),
            investing_cash_flow=_to_float(
                data.investing_cash_flow
            ),
            financing_cash_flow=_to_float(
                data.financing_cash_flow
            ),
            depreciation_and_amortization=_to_float(
                data.depreciation_and_amortization
            ),
            stock_based_compensation=_to_float(
                data.stock_based_compensation
            ),
            dividends_paid=_to_float(
                data.dividends_paid
            ),
            share_repurchases=_to_float(
                data.share_repurchases
            ),
            net_change_in_cash=_to_float(
                data.net_change_in_cash
            ),
        )