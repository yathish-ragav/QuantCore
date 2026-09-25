from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLAlchemyEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base
from quantcore.models.provenance import DATA_SOURCE_ENUM, DataSource, ProvenanceMixin
from quantcore.core.enums import SecurityType


class SecurityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


SECURITY_TYPE_ENUM = SQLAlchemyEnum(
    SecurityType,
    name="security_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


class Security(ProvenanceMixin, Base):
    __tablename__ = "securities"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "symbol",
            "exchange",
            name="uq_security_company_symbol_exchange",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    exchange: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    security_type: Mapped[SecurityType] = mapped_column(
        SECURITY_TYPE_ENUM,
        nullable=False,
        default=SecurityType.UNKNOWN,
        server_default=SecurityType.UNKNOWN.value,
        index=True,
    )

    security_type_source: Mapped[DataSource | None] = mapped_column(
        DATA_SOURCE_ENUM,
        nullable=True,
        index=True,
    )

    security_type_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    security_type_source_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    status: Mapped[SecurityStatus] = mapped_column(
        String(20),
        nullable=False,
        default=SecurityStatus.ACTIVE,
        server_default=SecurityStatus.ACTIVE.value,
        index=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
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

    identifiers = relationship(
        "SecurityIdentifier",
        back_populates="security",
        cascade="all, delete-orphan",
    )

    identifier_history = relationship(
        "SecurityIdentifierHistory",
        back_populates="security",
        cascade="all, delete-orphan",
    )

    classification_history = relationship(
        "SecurityClassificationHistory",
        back_populates="security",
        cascade="all, delete-orphan",
    )

    corporate_actions = relationship(
        "CorporateAction",
        back_populates="security",
        cascade="all, delete-orphan",
        foreign_keys="CorporateAction.security_id",
    )
