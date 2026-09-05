from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from quantcore.db.database import Base
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.models.ingestion import DATASET_ENUM


class IngestionSchedule(Base):
    """Persistent schedule definition for creating ingestion jobs.

    A schedule only decides *when* a durable ingestion job should be created.
    Execution remains owned by ``IngestionExecutionService`` and its workers.
    """

    __tablename__ = "ingestion_schedules"

    __table_args__ = (
        UniqueConstraint("name", name="uq_ingestion_schedule_name"),
        CheckConstraint(
            "interval_seconds >= 60",
            name="ck_ingestion_schedule_interval_positive",
        ),
        CheckConstraint(
            "target_limit IS NULL OR target_limit > 0",
            name="ck_ingestion_schedule_limit_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    dataset: Mapped[IngestionDataset] = mapped_column(
        DATASET_ENUM,
        nullable=False,
        index=True,
    )

    symbols: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    target_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    only_stale: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )

    interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        index=True,
    )

    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

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
