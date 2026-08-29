from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base


class ResearchObservation(Base):
    """Immutable, PIT-bound derived research observation."""

    __tablename__ = "research_observations"

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "as_of",
            "observation_key",
            "definition_version",
            name="uq_research_observation_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    as_of: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    observation_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    definition_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    value_numeric: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    value_text: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    unit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    input_manifest: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    input_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    security = relationship("Security")
