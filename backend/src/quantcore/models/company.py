from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)

    symbol: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255))

    sector: Mapped[str] = mapped_column(String(255))

    industry: Mapped[str] = mapped_column(String(255))

    country: Mapped[str] = mapped_column(String(100))

    website: Mapped[str] = mapped_column(String(500))

    market_cap: Mapped[int] = mapped_column(
        BigInteger,
        nullable=True,
    )

    prices = relationship(
        "Price",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    news = relationship(
    "News",
    back_populates="company",
    cascade="all, delete-orphan",
)