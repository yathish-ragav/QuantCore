from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class MarketIndexDataLoadStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MarketIndexDataLoad(Base):
    """Immutable audit record for one authorized index membership load."""

    __tablename__ = "market_index_data_loads"

    __table_args__ = (
        UniqueConstraint(
            "index_id",
            "data_source_id",
            "fingerprint",
            name="uq_market_index_data_load_fingerprint",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    index_id: Mapped[int] = mapped_column(
        ForeignKey("market_indexes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_source_id: Mapped[int] = mapped_column(
        ForeignKey("market_index_data_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[MarketIndexDataLoadStatus] = mapped_column(
        String(20), nullable=False
    )
    records_received: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    records_imported: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    index = relationship("MarketIndex", back_populates="data_loads")
    data_source = relationship("MarketIndexDataSource", back_populates="loads")
