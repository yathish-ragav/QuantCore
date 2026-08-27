from datetime import date, datetime
from decimal import Decimal
import hashlib

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quantcore.db.database import Base
from quantcore.models.provenance import ProvenanceMixin


def build_sec_xbrl_fact_identity_hash(
    *,
    company_id: int,
    accession_number: str,
    taxonomy: str,
    concept: str,
    unit: str,
    period_start: date | None,
    period_end: date,
    frame: str,
    qtrs: int,
    value: Decimal,
) -> str:
    payload = "\x1f".join(
        str(part) for part in (
            company_id, accession_number, taxonomy, concept, unit,
            period_start.isoformat() if period_start else "",
            period_end.isoformat(), frame, qtrs,
            format(value.normalize(), "f"),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SECXBRLFactObservation(ProvenanceMixin, Base):
    """Immutable SEC XBRL fact observation; revisions remain separate rows."""

    __tablename__ = "sec_xbrl_fact_observations"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "accession_number",
            "taxonomy",
            "concept",
            "unit",
            "period_start",
            "period_end",
            "frame",
            "qtrs",
            "value",
            name="uq_sec_xbrl_fact_observation_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    identity_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filing_id: Mapped[int | None] = mapped_column(
        ForeignKey("sec_filings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    accession_number: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True
    )
    taxonomy: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    concept: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    value: Mapped[Decimal] = mapped_column(
        Numeric(60, 18), nullable=False
    )

    period_start: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    filed_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    form: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    fiscal_period: Mapped[str | None] = mapped_column(String(10), nullable=True)
    frame: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="", index=True)
    qtrs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    decimals: Mapped[str | None] = mapped_column(String(40), nullable=True)

    company = relationship("Company")
    filing = relationship("SECFiling")
