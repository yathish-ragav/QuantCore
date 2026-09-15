from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLAlchemyEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from quantcore.db.database import Base


class UniverseSyncRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class UniverseSyncRun(Base):
    """Persistent execution record for the managed security-universe sync."""

    __tablename__ = "universe_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[UniverseSyncRunStatus] = mapped_column(
        SQLAlchemyEnum(
            UniverseSyncRunStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    records_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    active_companies: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    active_securities: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    inactive_securities: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    error: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )
