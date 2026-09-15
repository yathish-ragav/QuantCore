from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from quantcore.db.database import Base
from quantcore.models.company import Company
from quantcore.models.market_index import MarketIndex, MarketIndexConstituent
from quantcore.models.security import Security, SecurityStatus
from quantcore.repositories.market_index_repository import MarketIndexRepository


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Company.__table__,
            Security.__table__,
            MarketIndex.__table__,
            MarketIndexConstituent.__table__,
        ],
    )
    return engine, Session(engine)


def test_get_constituents_as_of_applies_effective_and_knowledge_boundaries():
    engine, session = make_session()
    try:
        company = Company(
            cik="0000000001",
            name="Example",
            sector="",
            industry="",
            country="",
            website="",
        )
        session.add(company)
        session.flush()

        known_security = Security(
            company_id=company.id,
            symbol="KNOWN",
            exchange="NASDAQ",
            status=SecurityStatus.ACTIVE,
        )
        future_known_security = Security(
            company_id=company.id,
            symbol="LATER",
            exchange="NASDAQ",
            status=SecurityStatus.ACTIVE,
        )
        session.add_all([known_security, future_known_security])
        session.flush()

        index = MarketIndex(
            key="TEST",
            name="Test Index",
            provider="licensed-provider",
        )
        session.add(index)
        session.flush()

        session.add_all(
            [
                MarketIndexConstituent(
                    index_id=index.id,
                    security_id=known_security.id,
                    effective_from=date(2020, 1, 1),
                    effective_to=None,
                    known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
                    observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                MarketIndexConstituent(
                    index_id=index.id,
                    security_id=future_known_security.id,
                    effective_from=date(2020, 1, 1),
                    effective_to=None,
                    known_at=datetime(2020, 7, 1, tzinfo=timezone.utc),
                    observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()

        repository = MarketIndexRepository(session)
        result = repository.get_constituents_as_of(
            index.id,
            effective_on=date(2020, 6, 1),
            known_at=datetime(2020, 6, 1, tzinfo=timezone.utc),
        )

        assert [item.security_id for item in result] == [known_security.id]
    finally:
        session.close()
        engine.dispose()


def test_get_constituents_as_of_treats_effective_to_as_exclusive():
    engine, session = make_session()
    try:
        company = Company(
            cik="0000000002",
            name="Example",
            sector="",
            industry="",
            country="",
            website="",
        )
        session.add(company)
        session.flush()
        security = Security(
            company_id=company.id,
            symbol="TEST",
            exchange="NASDAQ",
            status=SecurityStatus.ACTIVE,
        )
        session.add(security)
        session.flush()
        index = MarketIndex(key="TEST2", name="Test Index 2", provider="provider")
        session.add(index)
        session.flush()
        session.add(
            MarketIndexConstituent(
                index_id=index.id,
                security_id=security.id,
                effective_from=date(2020, 1, 1),
                effective_to=date(2021, 1, 1),
                known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
                observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )
        session.commit()

        repository = MarketIndexRepository(session)
        assert repository.get_constituents_as_of(
            index.id,
            effective_on=date(2020, 12, 31),
            known_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )
        assert repository.get_constituents_as_of(
            index.id,
            effective_on=date(2021, 1, 1),
            known_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
        ) == []
    finally:
        session.close()
        engine.dispose()
