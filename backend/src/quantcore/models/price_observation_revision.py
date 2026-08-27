from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Enum as SQLAlchemyEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.core.enums import PriceBasis
from quantcore.db.database import Base
from quantcore.models.provenance import DATA_SOURCE_ENUM, DataSource


PRICE_BASIS_ENUM = SQLAlchemyEnum(
    PriceBasis,
    name="price_basis",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


class PriceObservationRevision(Base):
    """Immutable snapshot of a market-price observation as known at fetch time."""

    __tablename__ = "price_observation_revisions"

    __table_args__ = (
        UniqueConstraint(
            "price_id",
            "revision_number",
            name="uq_price_observation_revision_price_revision",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    price_id: Mapped[int] = mapped_column(
        ForeignKey("prices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    adjusted_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_basis: Mapped[PriceBasis] = mapped_column(
        PRICE_BASIS_ENUM,
        nullable=False,
    )
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dividends: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stock_splits: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    source: Mapped[DataSource | None] = mapped_column(
        DATA_SOURCE_ENUM,
        nullable=True,
    )

    known_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    price = relationship("Price", back_populates="revisions")
