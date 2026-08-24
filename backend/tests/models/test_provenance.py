from datetime import datetime, timezone

from quantcore.models.cash_flow_statement import CashFlowStatement
from quantcore.models.income_statement import IncomeStatement
from quantcore.models.news import News
from quantcore.models.price import Price
from quantcore.models.provenance import (
    CompanyField,
    CompanyFieldProvenance,
    DataSource,
)
from quantcore.models.security import Security


def test_data_source_values_are_stable():
    assert DataSource.SEC.value == "SEC"
    assert DataSource.FMP.value == "FMP"
    assert DataSource.YAHOO.value == "YAHOO"


def test_company_field_values_match_company_columns():
    assert {
        field.value
        for field in CompanyField
    } == {
        "cik",
        "name",
        "sector",
        "industry",
        "country",
        "website",
        "market_cap",
    }


def test_provenance_columns_exist_on_provider_owned_models():

    for model in (
        Price,
        IncomeStatement,
        CashFlowStatement,
        News,
        Security,
    ):
        assert "source" in model.__table__.c
        assert "fetched_at" in model.__table__.c
        assert "source_reference" in model.__table__.c


def test_company_field_provenance_has_real_company_foreign_key():

    foreign_keys = CompanyFieldProvenance.__table__.foreign_keys

    assert len(foreign_keys) == 1
    assert next(iter(foreign_keys)).target_fullname == "companies.id"


def test_company_field_provenance_is_unique_per_company_field():

    constraints = CompanyFieldProvenance.__table__.constraints

    assert any(
        constraint.name
        == "uq_company_field_provenance_company_field"
        for constraint in constraints
    )
