from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class IndexSourceAuthority(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    REDISTRIBUTOR = "REDISTRIBUTOR"
    SECONDARY = "SECONDARY"


class IndexLicenseStatus(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    EXPIRED = "EXPIRED"
    RESTRICTED = "RESTRICTED"


class MarketIndexDataSource(Base):
    """Operational registry for index data sources and usage rights.

    This table records the licensing decision that permits an index feed to be
    persisted. It deliberately does not attempt to encode legal advice; the
    referenced agreement/terms remain the source of truth.
    """

    __tablename__ = "market_index_data_sources"

    __table_args__ = (
        UniqueConstraint("key", name="uq_market_index_data_sources_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset: Mapped[str] = mapped_column(String(255), nullable=False)
    authority: Mapped[IndexSourceAuthority] = mapped_column(
        String(30), nullable=False
    )
    license_status: Mapped[IndexLicenseStatus] = mapped_column(
        String(30), nullable=False, default=IndexLicenseStatus.NOT_REVIEWED
    )
    storage_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    display_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    redistribution_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    terms_reference: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    license_reference: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    attribution_text: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    indexes = relationship("MarketIndex", back_populates="data_source")
    loads = relationship("MarketIndexDataLoad", back_populates="data_source")
