from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as SQLAlchemyEnum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.core.enums import CorporateActionType
from quantcore.models.provenance import DATA_SOURCE_ENUM, DataSource
from quantcore.db.database import Base


CORPORATE_ACTION_TYPE_ENUM = SQLAlchemyEnum(
    CorporateActionType,
    name="corporate_action_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum: [member.value for member in enum],
)


class CorporateActionRevision(Base):
    """Immutable snapshot of a corporate action as known by QuantCore."""

    __tablename__ = "corporate_action_revisions"

    __table_args__ = (
        UniqueConstraint(
            "action_id",
            "revision_number",
            name="uq_corporate_action_revision_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(
        ForeignKey("corporate_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    action_type: Mapped[CorporateActionType] = mapped_column(
        CORPORATE_ACTION_TYPE_ENUM, nullable=False, index=True
    )
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    split_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[DataSource | None] = mapped_column(DATA_SOURCE_ENUM, nullable=True)
    known_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    action = relationship("CorporateAction")
    security = relationship("Security")
