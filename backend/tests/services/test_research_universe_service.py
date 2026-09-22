from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quantcore.core.enums import SecurityType
from quantcore.core.exceptions import InvalidInputError
from quantcore.db.database import Base
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.models.company import Company
from quantcore.models.ingestion import IngestionScope, IngestionState
from quantcore.models.provenance import DataSource
from quantcore.models.security import Security
from quantcore.models.security_identifier_history import SecurityIdentifierHistory
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


def test_current_ready_rejects_future_success_timestamp(db_session):
    now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    future = _security(db_session, "FUTURE")
    db_session.add(
        IngestionState(
            dataset=IngestionDataset.PRICE_HISTORY,
            scope=IngestionScope.SECURITY,
            security_id=future.id,
            last_success_at=now + timedelta(minutes=1),
        )
    )
    db_session.commit()

    result = ResearchUniverseService(db_session).current_ready(as_of=now)

    assert result.security_ids == ()


def test_listings_as_of_applies_latest_known_backdated_revision_before_effective_filter(
    db_session,
):
    security = _security(db_session, "OLD")
    known_early = datetime(2020, 1, 1, tzinfo=timezone.utc)
    known_late = datetime(2021, 1, 1, tzinfo=timezone.utc)

    db_session.add_all(
        [
            SecurityIdentifierHistory(
                security_id=security.id,
                symbol="OLD",
                exchange="NASDAQ",
                effective_from=date(2019, 1, 1),
                effective_to=None,
                known_at=known_early,
                first_seen_at=known_early,
                last_seen_at=known_early,
                is_current=False,
            ),
            SecurityIdentifierHistory(
                security_id=security.id,
                symbol="OLD",
                exchange="NASDAQ",
                effective_from=date(2019, 1, 1),
                effective_to=date(2020, 6, 1),
                known_at=known_late,
                first_seen_at=known_early,
                last_seen_at=known_late,
                is_current=False,
            ),
        ]
    )
    db_session.commit()

    service = ResearchUniverseService(db_session)

    before_revision = service.listings_as_of(
        effective_on=date(2020, 7, 1),
        known_at=datetime(2020, 6, 1, tzinfo=timezone.utc),
    )
    after_revision = service.listings_as_of(
        effective_on=date(2020, 7, 1),
        known_at=known_late,
    )

    assert before_revision.security_ids == (security.id,)
    assert after_revision.security_ids == ()



def test_current_common_stock_cohort_is_deterministic_and_provider_classified(db_session):
    first = _security(db_session, "AAPL")
    second = _security(db_session, "MSFT")
    third = _security(db_session, "ETF1", SecurityType.ETF)
    for security in (first, second, third):
        security.security_type_source = DataSource.MASSIVE
        security.security_type_fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db_session.commit()

    cohort = ResearchUniverseService(db_session).current_common_stock_cohort(size=2)

    assert cohort.size == 2
    assert cohort.symbols == ("AAPL", "MSFT")
    assert cohort.security_ids == (first.id, second.id)
    assert cohort.selection == "CURRENT_CLASSIFIED_COMMON_STOCK_COHORT"
    assert len(cohort.fingerprint) == 64
    assert cohort.fingerprint == (
        ResearchUniverseService(db_session)
        .current_common_stock_cohort(size=2)
        .fingerprint
    )


def test_current_common_stock_cohort_fails_closed_when_insufficient(db_session):
    security = _security(db_session, "AAPL")
    security.security_type_source = DataSource.MASSIVE
    security.security_type_fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db_session.commit()

    with pytest.raises(
        InvalidInputError,
        match="only 1 currently classified common stocks",
    ):
        ResearchUniverseService(db_session).current_common_stock_cohort(size=2)
