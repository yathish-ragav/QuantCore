from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quantcore.core.enums import SecurityType
from quantcore.core.exceptions import InvalidInputError
from quantcore.db.database import Base
from quantcore.ingestion.datasets import IngestionDataset
from quantcore.models.company import Company
from quantcore.models.financial_statement_revision import FinancialStatementRevision
from quantcore.models.price import Price
from quantcore.models.price_observation_revision import PriceObservationRevision
from quantcore.models.security_classification_history import SecurityClassificationHistory
from quantcore.models.ingestion import IngestionScope, IngestionState
from quantcore.models.provenance import DataSource
from quantcore.models.security import Security, SecurityStatus
from quantcore.models.security_identifier_history import SecurityIdentifierHistory
from quantcore.core.enums import FinancialPeriodType, FinancialStatementType, PriceBasis
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
    db_session.add(
        Price(
            security_id=ready.id,
            date=datetime(2026, 6, 15),
            open=100.0, high=101.0, low=99.0, close=100.5,
            adjusted_close=100.5, price_basis=PriceBasis.ADJUSTED, volume=1000,
            dividends=0.0, stock_splits=0.0,
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


def test_current_ready_requires_persisted_price_coverage(db_session):
    now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    ready_state_only = _security(db_session, "STATEONLY")
    db_session.add(
        IngestionState(
            dataset=IngestionDataset.PRICE_HISTORY,
            scope=IngestionScope.SECURITY,
            security_id=ready_state_only.id,
            last_success_at=now,
        )
    )
    db_session.commit()

    result = ResearchUniverseService(db_session).current_ready(as_of=now)

    assert result.security_ids == ()


def test_current_ready_allows_legitimate_empty_news_dataset(db_session):
    now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    security = _security(db_session, "NEWSZERO")
    db_session.add(
        IngestionState(
            dataset=IngestionDataset.NEWS,
            scope=IngestionScope.COMPANY,
            company_id=security.company_id,
            last_success_at=now,
        )
    )
    db_session.commit()

    result = ResearchUniverseService(db_session).current_ready(
        required_datasets=(IngestionDataset.NEWS,),
        as_of=now,
    )

    assert result.security_ids == (security.id,)


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


def _seed_historical_inputs(db, security, *, classification_known, price_known, financial_known):
    db.add(
        SecurityIdentifierHistory(
            security_id=security.id,
            symbol=security.symbol,
            exchange=security.exchange,
            effective_from=date(2020, 1, 1),
            effective_to=date(2025, 1, 1),
            known_at=classification_known,
            first_seen_at=classification_known,
            last_seen_at=classification_known,
            is_current=False,
        )
    )
    db.add(
        SecurityClassificationHistory(
            security_id=security.id,
            security_type=SecurityType.COMMON_STOCK,
            effective_from=date(2020, 1, 1),
            effective_to=None,
            known_at=classification_known,
            source=DataSource.MASSIVE,
            source_reference="test:classification",
            first_seen_at=classification_known,
            last_seen_at=classification_known,
            is_current=True,
        )
    )
    for statement_type, period_type in (
        (FinancialStatementType.INCOME, FinancialPeriodType.TTM),
        (FinancialStatementType.CASH_FLOW, FinancialPeriodType.TTM),
        (FinancialStatementType.BALANCE_SHEET, FinancialPeriodType.INSTANT),
    ):
        db.add(
            FinancialStatementRevision(
                statement_type=statement_type,
                statement_id=100 + len(db.new),
                company_id=security.company_id,
                revision_number=1,
                fiscal_date=date(2023, 12, 31),
                period_start=date(2024, 1, 1),
                fiscal_year=2024,
                fiscal_period="FY",
                period_type=period_type,
                filing_date=date(2025, 2, 1),
                filing_form="10-K",
                known_at=financial_known,
            )
        )
    price = Price(
        security_id=security.id,
        date=datetime(2024, 5, 1),
        open=100.0, high=101.0, low=99.0, close=100.5,
        adjusted_close=100.5, price_basis=PriceBasis.ADJUSTED, volume=1000,
        dividends=0.0, stock_splits=0.0,
    )
    db.add(price)
    db.flush()
    db.add(
        PriceObservationRevision(
            price_id=price.id, revision_number=1, date=price.date,
            open=price.open, high=price.high, low=price.low, close=price.close,
            adjusted_close=price.adjusted_close, price_basis=price.price_basis,
            volume=price.volume, dividends=0.0, stock_splits=0.0,
            source=DataSource.MASSIVE, known_at=price_known, source_reference="test:price",
        )
    )
    db.commit()


def test_historical_pit_eligible_intersects_listing_classification_and_revisions(db_session):
    security = _security(db_session, "HIST")
    security.status = SecurityStatus.INACTIVE
    classification_known = datetime(2024, 1, 2, tzinfo=timezone.utc)
    financial_known = datetime(2024, 2, 2, tzinfo=timezone.utc)
    price_known = datetime(2024, 2, 3, tzinfo=timezone.utc)
    _seed_historical_inputs(
        db_session, security,
        classification_known=classification_known,
        price_known=price_known,
        financial_known=financial_known,
    )

    result = ResearchUniverseService(db_session).historical_pit_eligible(
        effective_on=date(2024, 6, 1),
        known_at=datetime(2024, 6, 2, tzinfo=timezone.utc),
    )

    assert result.security_ids == (security.id,)
    assert result.selection == "HISTORICAL_PIT_ELIGIBLE"


def test_historical_pit_eligible_fails_closed_without_classification_history(db_session):
    security = _security(db_session, "NOC")
    db_session.add(
        SecurityIdentifierHistory(
            security_id=security.id, symbol=security.symbol, exchange=security.exchange,
            effective_from=date(2020, 1, 1), effective_to=None,
            known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
            first_seen_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
            last_seen_at=datetime(2020, 1, 2, tzinfo=timezone.utc), is_current=True,
        )
    )
    db_session.commit()

    result = ResearchUniverseService(db_session).historical_pit_eligible(
        effective_on=date(2024, 1, 1),
        known_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    assert result.security_ids == ()


def test_historical_pit_eligible_uses_classification_as_of_not_current_type(db_session):
    security = _security(db_session, "TRANS")
    security.security_type = SecurityType.ADR
    early = datetime(2020, 1, 2, tzinfo=timezone.utc)
    late = datetime(2025, 1, 2, tzinfo=timezone.utc)
    db_session.add(
        SecurityIdentifierHistory(
            security_id=security.id, symbol=security.symbol, exchange=security.exchange,
            effective_from=date(2020, 1, 1), effective_to=None, known_at=early,
            first_seen_at=early, last_seen_at=early, is_current=True,
        )
    )
    db_session.add_all([
        SecurityClassificationHistory(
            security_id=security.id, security_type=SecurityType.COMMON_STOCK,
            effective_from=date(2020, 1, 1), effective_to=date(2025, 1, 1),
            known_at=early, source=DataSource.MASSIVE, source_reference="test:old",
            first_seen_at=early, last_seen_at=early, is_current=False,
        ),
        SecurityClassificationHistory(
            security_id=security.id, security_type=SecurityType.ADR,
            effective_from=date(2025, 1, 1), effective_to=None, known_at=late,
            source=DataSource.MASSIVE, source_reference="test:new",
            first_seen_at=late, last_seen_at=late, is_current=True,
        ),
    ])
    db_session.commit()

    result = ResearchUniverseService(db_session).historical_pit_eligible(
        effective_on=date(2024, 6, 1),
        known_at=datetime(2024, 6, 2, tzinfo=timezone.utc),
        financial_requirements=(),
        require_price_history=False,
    )
    assert result.security_ids == (security.id,)


def test_historical_pit_eligible_rejects_future_known_financial_revision(db_session):
    security = _security(db_session, "FUT")
    early = datetime(2024, 1, 2, tzinfo=timezone.utc)
    future = datetime(2024, 7, 2, tzinfo=timezone.utc)
    db_session.add(
        SecurityIdentifierHistory(
            security_id=security.id, symbol=security.symbol, exchange=security.exchange,
            effective_from=date(2020, 1, 1), effective_to=None, known_at=early,
            first_seen_at=early, last_seen_at=early, is_current=True,
        )
    )
    db_session.add(
        SecurityClassificationHistory(
            security_id=security.id, security_type=SecurityType.COMMON_STOCK,
            effective_from=date(2020, 1, 1), effective_to=None, known_at=early,
            source=DataSource.MASSIVE, source_reference="test:classification",
            first_seen_at=early, last_seen_at=early, is_current=True,
        )
    )
    db_session.add(
        FinancialStatementRevision(
            statement_type=FinancialStatementType.INCOME, statement_id=1,
            company_id=security.company_id, revision_number=1,
            fiscal_date=date(2024, 6, 30), period_type=FinancialPeriodType.TTM,
            known_at=future,
        )
    )
    db_session.commit()

    result = ResearchUniverseService(db_session).historical_pit_eligible(
        effective_on=date(2024, 6, 30),
        known_at=datetime(2024, 6, 15, tzinfo=timezone.utc),
        financial_requirements=((FinancialStatementType.INCOME, FinancialPeriodType.TTM),),
        require_price_history=False,
    )
    assert result.security_ids == ()


def test_validate_historical_symbols_requires_pit_classification_and_revisions(db_session):
    security = _security(db_session, "ELIGIBLE")
    known = datetime(2024, 2, 3, tzinfo=timezone.utc)
    _seed_historical_inputs(
        db_session,
        security,
        classification_known=known,
        price_known=known,
        financial_known=known,
    )

    ResearchUniverseService(db_session).validate_historical_symbols(
        ("ELIGIBLE",),
        as_ofs=(datetime(2024, 6, 1, tzinfo=timezone.utc),),
    )


def test_validate_historical_symbols_rejects_missing_classification(db_session):
    security = _security(db_session, "NOCLASS")
    known = datetime(2024, 2, 3, tzinfo=timezone.utc)
    db_session.add(
        SecurityIdentifierHistory(
            security_id=security.id,
            symbol=security.symbol,
            exchange=security.exchange,
            effective_from=date(2020, 1, 1),
            effective_to=None,
            known_at=known,
            first_seen_at=known,
            last_seen_at=known,
            is_current=True,
        )
    )
    db_session.commit()

    with pytest.raises(InvalidInputError, match="NOCLASS"):
        ResearchUniverseService(db_session).validate_historical_symbols(
            ("NOCLASS",),
            as_ofs=(datetime(2024, 6, 1, tzinfo=timezone.utc),),
            financial_requirements=(),
            require_price_history=False,
        )


def test_validate_historical_symbols_does_not_use_current_status_or_type(db_session):
    security = _security(db_session, "DELISTED")
    security.status = SecurityStatus.INACTIVE
    security.security_type = SecurityType.ADR
    known = datetime(2024, 2, 3, tzinfo=timezone.utc)
    _seed_historical_inputs(
        db_session,
        security,
        classification_known=known,
        price_known=known,
        financial_known=known,
    )

    ResearchUniverseService(db_session).validate_historical_symbols(
        ("DELISTED",),
        as_ofs=(datetime(2024, 6, 1, tzinfo=timezone.utc),),
    )


def test_validate_historical_symbols_rejects_future_revision_coverage(db_session):
    security = _security(db_session, "FUTURECOVER")
    listing_known = datetime(2024, 1, 1, tzinfo=timezone.utc)
    future = datetime(2024, 7, 1, tzinfo=timezone.utc)
    db_session.add(
        SecurityIdentifierHistory(
            security_id=security.id,
            symbol=security.symbol,
            exchange=security.exchange,
            effective_from=date(2020, 1, 1),
            effective_to=None,
            known_at=listing_known,
            first_seen_at=listing_known,
            last_seen_at=listing_known,
            is_current=True,
        )
    )
    db_session.add(
        SecurityClassificationHistory(
            security_id=security.id,
            security_type=SecurityType.COMMON_STOCK,
            effective_from=date(2020, 1, 1),
            effective_to=None,
            known_at=listing_known,
            source=DataSource.MASSIVE,
            source_reference="test:classification",
            first_seen_at=listing_known,
            last_seen_at=listing_known,
            is_current=True,
        )
    )
    db_session.add(
        FinancialStatementRevision(
            statement_type=FinancialStatementType.INCOME,
            statement_id=1,
            company_id=security.company_id,
            revision_number=1,
            fiscal_date=date(2024, 6, 30),
            period_type=FinancialPeriodType.TTM,
            known_at=future,
        )
    )
    db_session.commit()

    with pytest.raises(InvalidInputError, match="FUTURECOVER"):
        ResearchUniverseService(db_session).validate_historical_symbols(
            ("FUTURECOVER",),
            as_ofs=(datetime(2024, 6, 15, tzinfo=timezone.utc),),
            financial_requirements=((FinancialStatementType.INCOME, FinancialPeriodType.TTM),),
            require_price_history=False,
        )
