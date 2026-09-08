from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SQLAlchemyEnum, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from quantcore.db.database import Base


class ResearchExperimentRunStatus(str, Enum):
    """Lifecycle state of one persisted research experiment run."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


RUN_STATUS_ENUM = SQLAlchemyEnum(
    ResearchExperimentRunStatus,
    name="research_experiment_run_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)


class ResearchExperimentRun(Base):
    """Durable identity and lifecycle record for one experiment execution."""

    __tablename__ = "research_experiment_runs"

    __table_args__ = (
        Index(
            "ix_research_experiment_runs_experiment_status_submitted_id",
            "experiment_key",
            "definition_version",
            "status",
            "submitted_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    run_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )

    experiment_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    definition_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    run_input_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    definition_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    status: Mapped[ResearchExperimentRunStatus] = mapped_column(
        RUN_STATUS_ENUM,
        nullable=False,
        default=ResearchExperimentRunStatus.QUEUED,
        server_default=ResearchExperimentRunStatus.QUEUED.value,
        index=True,
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

    error_summary: Mapped[str | None] = mapped_column(
        String(4000),
        nullable=True,
    )

    @staticmethod
    def new_run_id() -> str:
        """Return a unique opaque identifier suitable for external run references."""
        return uuid4().hex
