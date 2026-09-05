from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from quantcore.db.database import Base
from quantcore.ingestion.datasets import IngestionDataset, IngestionScope


class IngestionRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class IngestionJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


DATASET_ENUM = SQLAlchemyEnum(
    IngestionDataset,
    name="ingestion_dataset",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)

SCOPE_ENUM = SQLAlchemyEnum(
    IngestionScope,
    name="ingestion_scope",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)

RUN_STATUS_ENUM = SQLAlchemyEnum(
    IngestionRunStatus,
    name="ingestion_run_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)

JOB_STATUS_ENUM = SQLAlchemyEnum(
    IngestionJobStatus,
    name="ingestion_job_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)


class IngestionState(Base):
    """Latest ingestion outcome and freshness state for one dataset/entity."""

    __tablename__ = "ingestion_states"

    __table_args__ = (
        UniqueConstraint(
            "dataset",
            "company_id",
            name="uq_ingestion_state_dataset_company",
        ),
        UniqueConstraint(
            "dataset",
            "security_id",
            name="uq_ingestion_state_dataset_security",
        ),
        CheckConstraint(
            """
            (scope = 'company' AND company_id IS NOT NULL AND security_id IS NULL)
            OR
            (scope = 'security' AND security_id IS NOT NULL AND company_id IS NULL)
            """,
            name="ck_ingestion_state_scope_entity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    dataset: Mapped[IngestionDataset] = mapped_column(
        DATASET_ENUM,
        nullable=False,
        index=True,
    )

    scope: Mapped[IngestionScope] = mapped_column(
        SCOPE_ENUM,
        nullable=False,
        index=True,
    )

    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    security_id: Mapped[int | None] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_success_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    last_success_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    last_error: Mapped[str | None] = mapped_column(
        String(2000),
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


class IngestionJob(Base):
    """Persistent requested ingestion work item awaiting execution."""

    __tablename__ = "ingestion_jobs"

    __table_args__ = (
        CheckConstraint("target_limit IS NULL OR target_limit > 0", name="ck_ingestion_job_limit_positive"),
        CheckConstraint("attempt_count >= 0", name="ck_ingestion_job_attempt_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    dataset: Mapped[IngestionDataset] = mapped_column(
        DATASET_ENUM,
        nullable=False,
        index=True,
    )

    symbols: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    target_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    only_stale: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default="1",
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
    )

    request_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[IngestionJobStatus] = mapped_column(
        JOB_STATUS_ENUM,
        nullable=False,
        default=IngestionJobStatus.QUEUED,
        server_default=IngestionJobStatus.QUEUED.value,
        index=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    worker_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_summary: Mapped[str | None] = mapped_column(
        String(4000),
        nullable=True,
    )


class IngestionRun(Base):
    """Audit record for a coordinator execution."""

    __tablename__ = "ingestion_runs"

    __table_args__ = (
        UniqueConstraint(
            "dataset",
            "idempotency_key",
            name="uq_ingestion_run_dataset_idempotency",
        ),
        UniqueConstraint(
            "job_id",
            "attempt_number",
            name="uq_ingestion_run_job_attempt",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_ingestion_run_attempt_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    dataset: Mapped[IngestionDataset | None] = mapped_column(
        DATASET_ENUM,
        nullable=True,
        index=True,
    )

    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    request_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[IngestionRunStatus] = mapped_column(
        RUN_STATUS_ENUM,
        nullable=False,
        default=IngestionRunStatus.RUNNING,
        server_default=IngestionRunStatus.RUNNING.value,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    attempted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    succeeded: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    skipped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_summary: Mapped[str | None] = mapped_column(
        String(4000),
        nullable=True,
    )

    eligible: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
