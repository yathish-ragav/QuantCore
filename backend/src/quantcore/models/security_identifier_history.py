from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class SecurityIdentifierHistory(Base):
    """Observed ticker/exchange identities for a security over time."""

    __tablename__ = "security_identifier_history"

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "symbol",
            "exchange",
            name="uq_security_identifier_history_identity",
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
