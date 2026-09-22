from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from quantcore.db.database import Base
from quantcore.models.company import Company
from quantcore.models.security import Security
from quantcore.models.security_identifier import SecurityIdentifier
from quantcore.repositories.security_identifier_repository import SecurityIdentifierRepository
from quantcore.core.security_identity import SecurityIdentifierType


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[Company.__table__, Security.__table__, SecurityIdentifier.__table__],
    )
    return engine, Session(engine)


def seed_security(session, symbol):
    company = Company(
        cik=f"00000000{symbol[-1]}",
        name=symbol,
        sector="",
        industry="",
        country="",
        website="",
    )
    session.add(company)
    session.flush()
    security = Security(company_id=company.id, symbol=symbol, exchange="NASDAQ")
    session.add(security)
    session.flush()
    return security


def test_resolve_as_of_uses_latest_known_mapping():
    engine, session = make_session()
    try:
        security = seed_security(session, "TEST")
        session.add_all([
            SecurityIdentifier(
                security_id=security.id,
                identifier_type=SecurityIdentifierType.ISIN,
                namespace="ISIN",
                value="US0000000001",
                valid_from=date(2020, 1, 1),
                known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
                source="SEC",
            ),
            SecurityIdentifier(
                security_id=security.id,
                identifier_type=SecurityIdentifierType.ISIN,
                namespace="ISIN",
                value="US0000000002",
                valid_from=date(2022, 1, 1),
                known_at=datetime(2022, 1, 2, tzinfo=timezone.utc),
                source="SEC",
            ),
        ])
        session.commit()
        repo = SecurityIdentifierRepository(session)

        result = repo.resolve_as_of(
            SecurityIdentifierType.ISIN,
            "ISIN",
            "US0000000001",
            effective_on=date(2021, 1, 1),
            known_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )
        assert result is not None
        assert result.security_id == security.id
    finally:
        session.close()
        engine.dispose()


def test_get_for_security_as_of_applies_latest_known_backdated_closure_after_revision_selection():
    engine, session = make_session()
    try:
        security = seed_security(session, "TEST")
        early = datetime(2020, 1, 2, tzinfo=timezone.utc)
        late = datetime(2025, 7, 1, tzinfo=timezone.utc)
        session.add_all([
            SecurityIdentifier(
                security_id=security.id,
                identifier_type=SecurityIdentifierType.ISIN,
                namespace="ISIN",
                value="US0000000001",
                valid_from=date(2020, 1, 1),
                valid_to=None,
                known_at=early,
                source="SEC",
            ),
            SecurityIdentifier(
                security_id=security.id,
                identifier_type=SecurityIdentifierType.ISIN,
                namespace="ISIN",
                value="US0000000001",
                valid_from=date(2020, 1, 1),
                valid_to=date(2025, 6, 2),
                known_at=late,
                source="SEC",
            ),
        ])
        session.commit()
        repo = SecurityIdentifierRepository(session)

        before = repo.get_for_security_as_of(
            security.id,
            effective_on=date(2025, 6, 15),
            known_at=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )
        after = repo.get_for_security_as_of(
            security.id,
            effective_on=date(2025, 6, 15),
            known_at=datetime(2025, 7, 2, tzinfo=timezone.utc),
        )

        assert len(before) == 1
        assert before[0].valid_to is None
        assert after == []
    finally:
        session.close()
        engine.dispose()


def test_resolve_as_of_applies_latest_known_backdated_closure_after_revision_selection():
    engine, session = make_session()
    try:
        security = seed_security(session, "TEST")
        early = datetime(2020, 1, 2, tzinfo=timezone.utc)
        late = datetime(2025, 7, 1, tzinfo=timezone.utc)
        session.add_all([
            SecurityIdentifier(
                security_id=security.id,
                identifier_type=SecurityIdentifierType.ISIN,
                namespace="ISIN",
                value="US0000000001",
                valid_from=date(2020, 1, 1),
                valid_to=None,
                known_at=early,
                source="SEC",
            ),
            SecurityIdentifier(
                security_id=security.id,
                identifier_type=SecurityIdentifierType.ISIN,
                namespace="ISIN",
                value="US0000000001",
                valid_from=date(2020, 1, 1),
                valid_to=date(2025, 6, 2),
                known_at=late,
                source="SEC",
            ),
        ])
        session.commit()
        repo = SecurityIdentifierRepository(session)

        before = repo.resolve_as_of(
            SecurityIdentifierType.ISIN, "ISIN", "US0000000001",
            effective_on=date(2025, 6, 15),
            known_at=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )
        after = repo.resolve_as_of(
            SecurityIdentifierType.ISIN, "ISIN", "US0000000001",
            effective_on=date(2025, 6, 15),
            known_at=datetime(2025, 7, 2, tzinfo=timezone.utc),
        )

        assert before is not None
        assert before.valid_to is None
        assert after is None
    finally:
        session.close()
        engine.dispose()
