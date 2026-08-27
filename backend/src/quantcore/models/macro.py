from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SQLAlchemyEnum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base
from quantcore.models.provenance import DataSource


MACRO_DATA_SOURCE_ENUM = SQLAlchemyEnum(
    DataSource,
    name="macro_data_source",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


class MacroSeries(Base):
    """Canonical identity and metadata for an external economic series."""

    __tablename__ = "macro_series"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "series_id",
            name="uq_macro_series_source_series_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source: Mapped[DataSource] = mapped_column(
        MACRO_DATA_SOURCE_ENUM,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency_short: Mapped[str | None] = mapped_column(String(20), nullable=True)
    units: Mapped[str] = mapped_column(String(255), nullable=False)
    units_short: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seasonal_adjustment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seasonal_adjustment_short: Mapped[str | None] = mapped_column(String(20), nullable=True)
    observation_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    observation_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    observations = relationship(
        "MacroObservation",
        back_populates="series",
        cascade="all, delete-orphan",
    )


class MacroObservation(Base):
    """Economic observation preserved with its point-in-time vintage snapshot."""

    __tablename__ = "macro_observations"

    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "observation_date",
            "vintage_date",
            name="uq_macro_observation_series_date_vintage",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(
        ForeignKey("macro_series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(60, 18), nullable=True)
    realtime_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    realtime_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    vintage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[DataSource] = mapped_column(
        MACRO_DATA_SOURCE_ENUM,
        nullable=False,
        index=True,
    )
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    series = relationship("MacroSeries", back_populates="observations")
