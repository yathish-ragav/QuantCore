from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base
from quantcore.models.provenance import ProvenanceMixin


class Security(ProvenanceMixin, Base):
    __tablename__ = "securities"

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            name="uq_security_symbol",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    exchange: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    company = relationship(
        "Company",
        back_populates="securities",
    )

    prices = relationship(
        "Price",
        back_populates="security",
        cascade="all, delete-orphan",
    )
