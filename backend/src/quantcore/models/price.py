from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Enum as SQLAlchemyEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base
from quantcore.models.provenance import ProvenanceMixin
from quantcore.core.enums import PriceBasis


PRICE_BASIS_ENUM = SQLAlchemyEnum(
    PriceBasis,
    name="price_basis",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


class Price(ProvenanceMixin, Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id"),
        nullable=False,
        index=True,
    )

    security = relationship(
        "Security",
        back_populates="prices",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    open: Mapped[float] = mapped_column(Float)

    high: Mapped[float] = mapped_column(Float)

    low: Mapped[float] = mapped_column(Float)

    close: Mapped[float] = mapped_column(Float)

    adjusted_close: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    price_basis: Mapped[PriceBasis] = mapped_column(
        PRICE_BASIS_ENUM,
        nullable=False,
        default=PriceBasis.UNADJUSTED,
    )

    volume: Mapped[int] = mapped_column(BigInteger)

    dividends: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    stock_splits: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    revisions = relationship(
        "PriceObservationRevision",
        back_populates="price",
        cascade="all, delete-orphan",
        order_by="PriceObservationRevision.revision_number",
    )


Index(
    "ix_prices_security_date",
    Price.security_id,
    Price.date,
    unique=True,
)