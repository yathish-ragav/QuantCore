from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)

    cik: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255))

    sector: Mapped[str | None] = mapped_column(String(255), nullable=True)

    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)

    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    market_cap: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    securities = relationship(
        "Security",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    news = relationship(
        "News",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    income_statements = relationship(
        "IncomeStatement",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    cash_flow_statements = relationship(
        "CashFlowStatement",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    balance_sheets = relationship(
        "BalanceSheet",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    sec_filings = relationship(
        "SECFiling",
        back_populates="company",
        cascade="all, delete-orphan",
    )
