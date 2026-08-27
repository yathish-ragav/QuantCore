from datetime import date

from sqlalchemy import Date, Enum as SQLAlchemyEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from quantcore.core.enums import FinancialPeriodType


FINANCIAL_PERIOD_TYPE_ENUM = SQLAlchemyEnum(
    FinancialPeriodType,
    name="financial_period_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)


class FinancialStatementMetadataMixin:
    """Persistent temporal and filing identity for financial statements."""

    period_start: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    fiscal_year: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )

    fiscal_period: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )

    period_type: Mapped[FinancialPeriodType] = mapped_column(
        FINANCIAL_PERIOD_TYPE_ENUM,
        nullable=False,
        default=FinancialPeriodType.ANNUAL,
        server_default=FinancialPeriodType.ANNUAL.value,
        index=True,
    )

    filing_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True
    )

    filing_form: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    accession_number: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True
    )
