from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.core.security_identity import SecurityIdentifierType
from quantcore.db.database import Base


class SecurityIdentifier(Base):
    """Point-in-time external identifier mapping for a security.

    ``valid_to`` is exclusive. ``known_at`` is the knowledge boundary used by
    historical research: a mapping is only visible to a research snapshot at
    or after the timestamp at which QuantCore learned it.
    """

    __tablename__ = "security_identifiers"

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "identifier_type",
            "namespace",
            "value",
            "valid_from",
            "known_at",
            name="uq_security_identifier_revision",
        ),
        CheckConstraint(
            "identifier_type IN ('CUSIP', 'ISIN', 'SEDOL', 'FIGI', 'LEI', 'VENDOR')",
            name="ck_security_identifier_type",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_security_identifier_valid_interval",
        ),
        Index(
            "ix_security_identifier_lookup",
            "identifier_type",
            "namespace",
            "value",
            "valid_from",
        ),
        Index(
            "ix_security_identifier_security_valid",
            "security_id",
            "identifier_type",
            "namespace",
            "valid_from",
            "valid_to",
        ),
        Index(
            "ix_security_identifier_known_at",
            "known_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    identifier_type: Mapped[SecurityIdentifierType] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    namespace: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    value: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    valid_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    valid_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    known_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    security = relationship(
        "Security",
        back_populates="identifiers",
    )
