from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.core.enums import SecurityType
from quantcore.db.database import Base
from quantcore.models.provenance import DataSource


SECURITY_TYPE_HISTORY_ENUM = SQLAlchemyEnum(
    SecurityType,
    name="security_type_history",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)

DATA_SOURCE_HISTORY_ENUM = SQLAlchemyEnum(
    DataSource,
    name="security_classification_source",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
    length=10,
)


class SecurityClassificationHistory(Base):
    """Bitemporal instrument classification observations.

    ``effective_from`` records the date from which QuantCore treats the
    classification as effective.  The current Massive source supplies an
    observation timestamp rather than an authoritative historical transition
    date, so new history begins on the observation date.  This deliberately
    does not backfill earlier dates from today's classification.
    """

    __tablename__ = "security_classification_history"

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "effective_from",
            "known_at",
            name="uq_security_classification_history_revision",
        ),
        Index(
            "ix_security_classification_history_effective",
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

    security_type: Mapped[SecurityType] = mapped_column(
        SECURITY_TYPE_HISTORY_ENUM,
        nullable=False,
        index=True,
    )

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    known_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    source: Mapped[DataSource | None] = mapped_column(
        DATA_SOURCE_HISTORY_ENUM,
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

    security = relationship("Security", back_populates="classification_history")
