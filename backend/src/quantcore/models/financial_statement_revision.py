from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum as SQLAlchemyEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.core.enums import FinancialPeriodType, FinancialStatementType
from quantcore.models.provenance import DataSource
from quantcore.db.database import Base


FINANCIAL_STATEMENT_TYPE_ENUM = SQLAlchemyEnum(
    FinancialStatementType,
    name="financial_statement_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)

FINANCIAL_PERIOD_TYPE_ENUM = SQLAlchemyEnum(
    FinancialPeriodType,
    name="financial_period_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)

DATA_SOURCE_ENUM = SQLAlchemyEnum(
    DataSource,
    name="data_source",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)


class FinancialStatementRevision(Base):
    """Immutable snapshot of a normalized financial statement as known by QuantCore."""

    __tablename__ = "financial_statement_revisions"

    __table_args__ = (
        UniqueConstraint(
            "statement_type",
            "statement_id",
            "revision_number",
            name="uq_financial_statement_revision_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    statement_type: Mapped[FinancialStatementType] = mapped_column(
        FINANCIAL_STATEMENT_TYPE_ENUM, nullable=False, index=True
    )
    statement_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)

    fiscal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_period: Mapped[str | None] = mapped_column(String(10), nullable=True)
    period_type: Mapped[FinancialPeriodType] = mapped_column(
        FINANCIAL_PERIOD_TYPE_ENUM, nullable=False, index=True
    )
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    filing_form: Mapped[str | None] = mapped_column(String(20), nullable=True)
    accession_number: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    # Income statement values
    total_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Balance-sheet values
    cash_and_cash_equivalents: Mapped[float | None] = mapped_column(Float, nullable=True)
    short_term_investments: Mapped[float | None] = mapped_column(Float, nullable=True)
    accounts_receivable: Mapped[float | None] = mapped_column(Float, nullable=True)
    inventory: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_current_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    property_plant_equipment_net: Mapped[float | None] = mapped_column(Float, nullable=True)
    goodwill: Mapped[float | None] = mapped_column(Float, nullable=True)
    intangible_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    accounts_payable: Mapped[float | None] = mapped_column(Float, nullable=True)
    short_term_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_current_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True)
    long_term_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    retained_earnings: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    working_capital: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Cash-flow values
    operating_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    capital_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    investing_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    financing_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    depreciation_and_amortization: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_based_compensation: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividends_paid: Mapped[float | None] = mapped_column(Float, nullable=True)
    share_repurchases: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_change_in_cash: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[DataSource | None] = mapped_column(DATA_SOURCE_ENUM, nullable=True)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    company = relationship("Company")
