from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from quantcore.models.sec_xbrl_fact import SECXBRLFactObservation


class SECXBRLFactRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_identity(
        self,
        *,
        company_id: int,
        accession_number: str,
        taxonomy: str,
        concept: str,
        unit: str,
        period_start: date | None,
        period_end: date,
        frame: str | None,
        qtrs: int | None,
        value: Decimal,
    ) -> SECXBRLFactObservation | None:
        return self.db.scalar(
            select(SECXBRLFactObservation).where(
                SECXBRLFactObservation.company_id == company_id,
                SECXBRLFactObservation.accession_number == accession_number,
                SECXBRLFactObservation.taxonomy == taxonomy,
                SECXBRLFactObservation.concept == concept,
                SECXBRLFactObservation.unit == unit,
                SECXBRLFactObservation.period_start == period_start,
                SECXBRLFactObservation.period_end == period_end,
                SECXBRLFactObservation.frame == frame,
                SECXBRLFactObservation.qtrs == qtrs,
                SECXBRLFactObservation.value == value,
            )
        )

    def get_for_company(
        self,
        company_id: int,
    ) -> list[SECXBRLFactObservation]:
        stmt = (
            select(SECXBRLFactObservation)
            .where(SECXBRLFactObservation.company_id == company_id)
            .order_by(
                SECXBRLFactObservation.filed_at.desc(),
                SECXBRLFactObservation.accession_number.desc(),
                SECXBRLFactObservation.id.desc(),
            )
        )
        return list(self.db.scalars(stmt).all())

    def get_latest_for_company_as_of(
        self,
        company_id: int,
        as_of: date,
    ) -> list[SECXBRLFactObservation]:
        """Return the latest filed revision for each fact-period identity as of a date."""
        ranked = (
            select(
                SECXBRLFactObservation,
                func.row_number()
                .over(
                    partition_by=(
                        SECXBRLFactObservation.taxonomy,
                        SECXBRLFactObservation.concept,
                        SECXBRLFactObservation.unit,
                        SECXBRLFactObservation.period_start,
                        SECXBRLFactObservation.period_end,
                        SECXBRLFactObservation.frame,
                        SECXBRLFactObservation.qtrs,
                    ),
                    order_by=(
                        SECXBRLFactObservation.accepted_at.desc().nullslast(),
                        SECXBRLFactObservation.filed_at.desc(),
                        SECXBRLFactObservation.accession_number.desc(),
                        SECXBRLFactObservation.id.desc(),
                    ),
                )
                .label("revision_rank"),
            )
            .where(
                SECXBRLFactObservation.company_id == company_id,
                SECXBRLFactObservation.filed_at <= as_of,
            )
            .subquery()
        )

        stmt = select(SECXBRLFactObservation).join(
            ranked,
            SECXBRLFactObservation.id == ranked.c.id,
        ).where(ranked.c.revision_rank == 1)

        return list(self.db.scalars(stmt).all())

    def create(self, **kwargs) -> SECXBRLFactObservation:
        observation = SECXBRLFactObservation(**kwargs)
        self.db.add(observation)
        return observation
