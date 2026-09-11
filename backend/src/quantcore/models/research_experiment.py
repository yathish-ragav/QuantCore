from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SQLAlchemyEnum, ForeignKey, Index, JSON, String, UniqueConstraint
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


class ResearchExperimentRunResult(Base):
    """Immutable persisted output produced by one completed experiment run."""

    __tablename__ = "research_experiment_run_results"

    id: Mapped[int] = mapped_column(primary_key=True)

    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("research_experiment_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    result_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    metrics: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    result_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ResearchExperimentComparisonResultRecord(Base):
    """Immutable persisted snapshot of one deterministic comparison result."""

    __tablename__ = "research_experiment_comparison_results"

    __table_args__ = (
        Index(
            "ix_research_experiment_comparison_results_comparison_recorded_id",
            "comparison_fingerprint",
            "recorded_at",
            "id",
        ),
        Index(
            "ix_research_experiment_comparison_results_selection_fingerprint",
            "selection_fingerprint",
        ),
        UniqueConstraint(
            "result_fingerprint",
            name="uq_research_experiment_comparison_results_result_fingerprint",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    comparison_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    selection_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    experiment_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    definition_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    comparison_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    result_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    result_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ResearchExperimentArtifact(Base):
    """Immutable descriptor and provenance record for one experiment artifact."""

    __tablename__ = "research_experiment_artifacts"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "artifact_fingerprint",
            name="uq_research_experiment_artifacts_run_fingerprint",
        ),
        Index(
            "ix_research_experiment_artifacts_run_created_id",
            "run_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_research_experiment_artifacts_content_hash",
            "content_hash",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    artifact_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )

    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("research_experiment_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )

    artifact_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    artifact_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    artifact_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
    )

    provenance: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def new_artifact_id() -> str:
        """Return a unique opaque identifier suitable for artifact references."""
        return uuid4().hex
