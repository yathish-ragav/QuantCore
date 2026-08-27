from datetime import date

from sqlalchemy import Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base
from quantcore.models.financial_statement import FinancialStatementMetadataMixin
from quantcore.models.provenance import ProvenanceMixin


class CashFlowStatement(FinancialStatementMetadataMixin, ProvenanceMixin, Base):
    __tablename__ = "cash_flow_statements"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_date",
            "period_type",
            name="uq_cash_flow_statement_company_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    company = relationship(
        "Company",
        back_populates="cash_flow_statements",
    )

    fiscal_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    operating_cash_flow: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    capital_expenditure: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    free_cash_flow: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    investing_cash_flow: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    financing_cash_flow: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    depreciation_and_amortization: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    stock_based_compensation: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    dividends_paid: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    share_repurchases: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    net_change_in_cash: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
