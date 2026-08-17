from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class IncomeStatement(Base):
    __tablename__ = "income_statements"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_date",
            name="uq_income_statement_company_fiscal_date",
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
        back_populates="income_statements",
    )

    fiscal_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    total_revenue: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    gross_profit: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    operating_income: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    net_income: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    eps: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    shares_outstanding: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )