from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from quantcore.db.database import Base


class MacroIngestionState(Base):
    """Latest ingestion outcome and freshness state for one macro series."""

    __tablename__ = "macro_ingestion_states"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "series_id",
            name="uq_macro_ingestion_state_source_series",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    series_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_vintage: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_success_records: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
