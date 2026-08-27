from datetime import date

from sqlalchemy import Date, Enum as SQLAlchemyEnum, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base
from quantcore.models.provenance import ProvenanceMixin
from quantcore.core.enums import CorporateActionType

CORPORATE_ACTION_TYPE_ENUM = SQLAlchemyEnum(
    CorporateActionType,
    name="corporate_action_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


class CorporateAction(ProvenanceMixin, Base):
    """Normalized, provider-provenanced corporate action."""

    __tablename__ = "corporate_actions"

    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "effective_date",
            "action_type",
            name="uq_corporate_action_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    action_type: Mapped[CorporateActionType] = mapped_column(
        CORPORATE_ACTION_TYPE_ENUM,
        nullable=False,
        index=True,
    )

    amount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    split_ratio: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    security = relationship(
        "Security",
        back_populates="corporate_actions",
    )
