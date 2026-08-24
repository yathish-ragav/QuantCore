from datetime import date

import pytest

from quantcore.processing.cleaner import DataCleaner
from quantcore.processing.transformer import DataTransformer
from quantcore.processing.validator import DataValidator
from quantcore.schemas.balance_sheet import BalanceSheetData


def make_data():
    return BalanceSheetData(
        fiscal_date=date(2024, 9, 28),
        cash_and_cash_equivalents=100,
        short_term_investments=50,
        accounts_receivable=75,
        inventory=125,
        total_current_assets=500,
        property_plant_equipment_net=300,
        goodwill=20,
        intangible_assets=30,
        total_assets=1000,
        accounts_payable=80,
        short_term_debt=100,
        total_current_liabilities=250,
        long_term_debt=300,
        total_liabilities=550,
        total_equity=450,
        retained_earnings=250,
        total_debt=400,
        net_debt=300,
        working_capital=250,
    )


def test_transformer_accepts_domain_object():
    data = make_data()
    assert DataTransformer.balance_sheet(data) is data


def test_transformer_accepts_dict():
    result = DataTransformer.balance_sheet(
        {
            "fiscal_date": "2024-09-28",
            "total_assets": 1000,
        }
    )
    assert result.fiscal_date == date(2024, 9, 28)
    assert result.total_assets == 1000


def test_transformer_rejects_invalid_type():
    with pytest.raises(TypeError, match="Balance sheet data"):
        DataTransformer.balance_sheet("invalid")


def test_transformer_list():
    result = DataTransformer.balance_sheets([make_data()])
    assert len(result) == 1


def test_cleaner_normalizes_numeric_values():
    data = make_data()
    data.total_assets = "1000"
    result = DataCleaner.clean_balance_sheet(data)
    assert result.total_assets == 1000.0


def test_validator_accepts_valid_statement():
    assert DataValidator.validate_balance_sheet(make_data()) is True


def test_validator_accepts_partial_statement():
    data = BalanceSheetData(
        fiscal_date=date(2024, 9, 28),
        total_assets=1000,
    )
    assert DataValidator.validate_balance_sheet(data) is True


def test_validator_rejects_non_finite_value():
    data = make_data()
    data.total_assets = float("nan")
    assert DataValidator.validate_balance_sheet(data) is False


def test_validator_rejects_invalid_date():
    data = make_data()
    data.fiscal_date = "2024-09-28"
    assert DataValidator.validate_balance_sheet(data) is False


def test_validator_list():
    assert DataValidator.validate_balance_sheets([make_data()]) is True
    assert DataValidator.validate_balance_sheets([]) is True
