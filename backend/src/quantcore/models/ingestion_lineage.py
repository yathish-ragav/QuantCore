from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.models.ingestion import DATASET_ENUM, SCOPE_ENUM
from quantcore.models.provenance import DATA_SOURCE_ENUM, DataSource
from quantcore.db.database import Base


class IngestionLineage(Base):
    """Successful ingestion execution-to-entity provenance edge.

    The row links a persisted ingestion outcome to the exact coordinator run
    that produced it. Dataset rows retain their own source references; this
    table intentionally provides the execution-level bridge rather than
    duplicating dataset-specific row identities.
    """

    __tablename__ = "ingestion_lineage"

    __table_args__ = (
        UniqueConstraint(
            "ingestion_run_id",
            "company_id",
            "security_id",
            name="uq_ingestion_lineage_run_entity",
        ),
        CheckConstraint(
            "records_processed >= 0",
            name="ck_ingestion_lineage_records_nonnegative",
        ),
        CheckConstraint(
            "(scope = 'company' AND company_id IS NOT NULL AND security_id IS NULL)"
            " OR (scope = 'security' AND security_id IS NOT NULL AND company_id IS NULL)",
            name="ck_ingestion_lineage_scope_entity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

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

    source: Mapped[DataSource | None] = mapped_column(
        DATA_SOURCE_ENUM,
        nullable=True,
        index=True,
    )

    source_reference: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    records_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ingestion_run = relationship("IngestionRun")
