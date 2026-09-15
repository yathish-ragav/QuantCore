from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class SecurityIdentifierHistory(Base):
    """Effective-dated ticker/exchange listing identities for a security."""

    __tablename__ = "security_identifier_history"

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "symbol",
            "exchange",
            "effective_from",
            "known_at",
            name="uq_security_listing_history_revision",
        ),
        Index(
            "ix_security_listing_history_effective",
            "security_id",
            "effective_from",
            "effective_to",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    exchange: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    known_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    is_current: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    security = relationship(
        "Security",
        back_populates="identifier_history",
    )
