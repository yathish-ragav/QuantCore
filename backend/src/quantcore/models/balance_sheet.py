from datetime import date

from sqlalchemy import Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base
from quantcore.models.provenance import ProvenanceMixin


class BalanceSheet(ProvenanceMixin, Base):
    __tablename__ = "balance_sheets"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_date",
            name="uq_balance_sheet_company_fiscal_date",
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
        back_populates="balance_sheets",
    )

    fiscal_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    cash_and_cash_equivalents: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    short_term_investments: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    accounts_receivable: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    inventory: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    total_current_assets: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    property_plant_equipment_net: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    goodwill: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    intangible_assets: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    total_assets: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    accounts_payable: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    short_term_debt: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    total_current_liabilities: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    long_term_debt: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    total_liabilities: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    total_equity: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    retained_earnings: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    total_debt: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    net_debt: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    working_capital: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
