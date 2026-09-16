from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quantcore.core.enums import SecurityType
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.models.company import Company
from quantcore.models.ingestion import IngestionScope, IngestionState
from quantcore.models.security import Security
from quantcore.models.security_identifier_history import SecurityIdentifierHistory
from quantcore.db.database import Base
from quantcore.services.research_universe_service import ResearchUniverseService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _security(db, symbol="AAPL", security_type=SecurityType.COMMON_STOCK):
    company = Company(cik=f"{abs(hash(symbol)) % 10_000_000_000:010d}", name="Test Company")
    db.add(company)
    db.flush()
    security = Security(
        company_id=company.id,
        symbol=symbol,
        exchange="NASDAQ",
        security_type=security_type,
    )
    db.add(security)
    db.flush()
    return security


def test_current_ready_requires_type_and_fresh_price(db_session):
    now = datetime.now(timezone.utc)
    ready = _security(db_session, "AAPL")
    not_common = _security(db_session, "ETF1", SecurityType.ETF)
    stale = _security(db_session, "STALE")
    for security in (ready, not_common, stale):
        db_session.add(
            IngestionState(
                dataset=IngestionDataset.PRICE_HISTORY,
                scope=IngestionScope.SECURITY,
                security_id=security.id,
                last_success_at=(now if security is not stale else now - timedelta(days=2)),
            )
        )
    db_session.commit()

    result = ResearchUniverseService(db_session).current_ready(as_of=now)

    assert result.security_ids == (ready.id,)
    assert result.selection == "CURRENT_RESEARCH_READY"


def test_listings_as_of_uses_known_at_and_effective_dates(db_session):
    security = _security(db_session, "OLD")
    known_early = datetime(2020, 1, 1, tzinfo=timezone.utc)
    known_late = datetime(2021, 1, 1, tzinfo=timezone.utc)
    db_session.add_all([
        SecurityIdentifierHistory(
            security_id=security.id,
            symbol="OLD",
            exchange="NASDAQ",
            effective_from=date(2019, 1, 1),
            effective_to=date(2020, 6, 1),
            known_at=known_early,
            first_seen_at=known_early,
            last_seen_at=known_early,
            is_current=False,
        ),
        SecurityIdentifierHistory(
            security_id=security.id,
            symbol="NEW",
            exchange="NASDAQ",
            effective_from=date(2020, 6, 1),
            effective_to=None,
            known_at=known_late,
            first_seen_at=known_late,
            last_seen_at=known_late,
            is_current=True,
        ),
    ])
    db_session.commit()

    service = ResearchUniverseService(db_session)
    early = service.listings_as_of(
        effective_on=date(2020, 3, 1),
        known_at=known_early,
    )
    late = service.listings_as_of(
        effective_on=date(2021, 3, 1),
        known_at=known_late,
    )

    assert early.security_ids == (security.id,)
    assert late.security_ids == (security.id,)
