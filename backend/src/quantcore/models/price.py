from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class Price(Base):
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

    volume: Mapped[int] = mapped_column(BigInteger)

    dividends: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    stock_splits: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )


Index(
    "ix_prices_security_date",
    Price.security_id,
    Price.date,
    unique=True,
)