from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.core.enums import FilingEventType
from quantcore.db.database import Base
from quantcore.models.provenance import ProvenanceMixin


FILING_EVENT_TYPE_ENUM = SQLAlchemyEnum(
    FilingEventType,
    name="filing_event_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)


class SECFiling(ProvenanceMixin, Base):
    """Immutable SEC filing identity and metadata."""

    __tablename__ = "sec_filings"

    id: Mapped[int] = mapped_column(primary_key=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    accession_number: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        unique=True,
        index=True,
    )

    filing_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    report_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    acceptance_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    form: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    act: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    file_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    film_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    items: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    primary_document: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    primary_doc_description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    is_xbrl: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_inline_xbrl: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    fiscal_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    fiscal_period: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    is_amendment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    filing_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    company = relationship(
        "Company",
        back_populates="sec_filings",
    )

    events = relationship(
        "FilingEvent",
        back_populates="filing",
        cascade="all, delete-orphan",
        order_by="FilingEvent.occurred_at",
    )


class FilingEvent(ProvenanceMixin, Base):
    """Immutable normalized lifecycle event for an SEC filing."""

    __tablename__ = "filing_events"

    __table_args__ = (
        UniqueConstraint(
            "filing_id",
            "event_type",
            "occurred_at",
            name="uq_filing_event_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    filing_id: Mapped[int] = mapped_column(
        ForeignKey("sec_filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[FilingEventType] = mapped_column(
        FILING_EVENT_TYPE_ENUM,
        nullable=False,
        index=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    filing = relationship(
        "SECFiling",
        back_populates="events",
    )
