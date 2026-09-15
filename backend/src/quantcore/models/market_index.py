from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index as SQLIndex, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class MarketIndex(Base):
    """Canonical identity and provenance metadata for a supported market index."""

    __tablename__ = "market_indexes"

    __table_args__ = (
        UniqueConstraint("key", name="uq_market_indexes_key"),
        SQLIndex("ix_market_indexes_provider_key", "provider", "key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    data_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("market_index_data_sources.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    methodology_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    data_source = relationship("MarketIndexDataSource", back_populates="indexes")
    data_loads = relationship("MarketIndexDataLoad", back_populates="index", cascade="all, delete-orphan")

    constituents = relationship(
        "MarketIndexConstituent",
        back_populates="index",
        cascade="all, delete-orphan",
    )


class MarketIndexConstituent(Base):
    """Point-in-time membership interval for one security in one market index.

    ``effective_to`` is exclusive. A null ``effective_to`` means the membership
    remains effective until superseded by a later interval.
    """

    __tablename__ = "market_index_constituents"

    __table_args__ = (
        UniqueConstraint(
            "index_id",
            "security_id",
            "effective_from",
            "known_at",
            name="uq_market_index_constituents_start_known_at",
        ),
        SQLIndex(
            "ix_market_index_constituents_index_effective",
            "index_id",
            "effective_from",
            "effective_to",
        ),
        SQLIndex(
            "ix_market_index_constituents_security_effective",
            "security_id",
            "effective_from",
            "effective_to",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    index_id: Mapped[int] = mapped_column(
        ForeignKey("market_indexes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 10),
        nullable=True,
    )
    source_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    data_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("market_index_data_sources.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # ``known_at`` is the source-knowledge boundary used for PIT resolution.
    # ``observed_at`` records when QuantCore ingested the membership.
    known_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    index = relationship("MarketIndex", back_populates="constituents")
    security = relationship("Security")
    data_source = relationship("MarketIndexDataSource")
