from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLAlchemyEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from quantcore.db.database import Base


class DataSource(str, Enum):
    """Known external data sources currently used by QuantCore."""

    SEC = "SEC"
    FMP = "FMP"
    YAHOO = "YAHOO"


class CompanyField(str, Enum):
    """Company fields whose provider ownership is tracked."""

    CIK = "cik"
    NAME = "name"
    SECTOR = "sector"
    INDUSTRY = "industry"
    COUNTRY = "country"
    WEBSITE = "website"
    MARKET_CAP = "market_cap"


DATA_SOURCE_ENUM = SQLAlchemyEnum(
    DataSource,
    name="data_source",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


COMPANY_FIELD_ENUM = SQLAlchemyEnum(
    CompanyField,
    name="company_field",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)


class ProvenanceMixin:
    """Reusable row-level provenance for provider-owned datasets."""

    source: Mapped[DataSource | None] = mapped_column(
        DATA_SOURCE_ENUM,
        nullable=True,
        index=True,
    )

    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )


class CompanyFieldProvenance(Base):
    """Current provider ownership for an individual Company field."""

    __tablename__ = "company_field_provenance"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "field_name",
            name="uq_company_field_provenance_company_field",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    field_name: Mapped[CompanyField] = mapped_column(
        COMPANY_FIELD_ENUM,
        nullable=False,
        index=True,
    )

    source: Mapped[DataSource] = mapped_column(
        DATA_SOURCE_ENUM,
        nullable=False,
        index=True,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
