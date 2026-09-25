from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quantcore.core.enums import SecurityType
from quantcore.models.company import Company
from quantcore.models.security import Security, SecurityStatus
from quantcore.models.security_classification_history import SecurityClassificationHistory
from quantcore.models.provenance import DataSource
from quantcore.services.security_classification_service import (
    SecurityClassificationService,
)
from quantcore.universe.models import UniverseSecurityClassification
from quantcore.db.database import Base


class FakeProvider:
    def __init__(self, rows):
        self.rows = rows

    def fetch(self):
        return self.rows


def test_security_classification_updates_known_types_and_preserves_unknown():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        company = Company(cik="0000320193", name="Apple Inc.")
        db.add(company)
        db.flush()
        security = Security(
            company_id=company.id,
            symbol="AAPL",
            exchange="NASDAQ",
            security_type=SecurityType.UNKNOWN,
        )
        db.add(security)
        db.commit()

        observed_at = datetime.now(timezone.utc)
        provider = FakeProvider(
            [
                UniverseSecurityClassification(
                    cik="0000320193",
                    symbol="AAPL",
                    security_type=SecurityType.COMMON_STOCK,
                    source="MASSIVE",
                    observed_at=observed_at,
                    source_reference="MASSIVE:TICKER:AAPL:0000320193",
                )
            ]
        )

        result = SecurityClassificationService(db, provider).sync()

        db.refresh(security)
        assert result.eligible == 1
        assert result.classified == 1
        assert result.unknown == 0
        assert result.unmatched == 0
        assert security.security_type is SecurityType.COMMON_STOCK
        assert security.security_type_source is DataSource.MASSIVE
        assert security.security_type_source_reference == (
            "MASSIVE:TICKER:AAPL:0000320193"
        )
        history = db.query(SecurityClassificationHistory).all()
        assert len(history) == 1
        assert history[0].security_type is SecurityType.COMMON_STOCK
        assert history[0].effective_from == observed_at.date()
        assert history[0].known_at.replace(tzinfo=timezone.utc) == observed_at
    finally:
        db.close()
        engine.dispose()


def test_security_classification_does_not_guess_unmatched_security():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        company = Company(cik="0000320193", name="Apple Inc.")
        db.add(company)
        db.flush()
        security = Security(
            company_id=company.id,
            symbol="AAPL",
            exchange="NASDAQ",
            security_type=SecurityType.UNKNOWN,
        )
        db.add(security)
        db.commit()

        result = SecurityClassificationService(
            db,
            FakeProvider([]),
        ).sync()

        db.refresh(security)
        assert result.eligible == 1
        assert result.classified == 0
        assert result.unknown == 0
        assert result.unmatched == 1
        assert security.security_type is SecurityType.UNKNOWN
        assert security.security_type_source is None
    finally:
        db.close()
        engine.dispose()



def test_security_classification_reconciles_safe_vendor_symbol_formatting():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        company = Company(cik="0000000001", name="Example")
        db.add(company)
        db.flush()
        securities = [
            Security(company_id=company.id, symbol="ABR-PD", exchange="NYSE"),
            Security(company_id=company.id, symbol="AAC-UN", exchange="NYSE"),
            Security(company_id=company.id, symbol="AAC-WT", exchange="NYSE"),
            Security(company_id=company.id, symbol="AGM-A", exchange="NYSE"),
        ]
        db.add_all(securities)
        db.commit()

        observed_at = datetime.now(timezone.utc)
        provider = FakeProvider(
            [
                UniverseSecurityClassification(
                    "0000000001", "ABRPD", SecurityType.PREFERRED_STOCK,
                    "MASSIVE", observed_at, "ref-ab", "PFD",
                ),
                UniverseSecurityClassification(
                    "0000000001", "AAC.U", SecurityType.UNIT,
                    "MASSIVE", observed_at, "ref-aac-u", "UNIT",
                ),
                UniverseSecurityClassification(
                    "0000000001", "AAC.WS", SecurityType.WARRANT,
                    "MASSIVE", observed_at, "ref-aac-w", "WARRANT",
                ),
                UniverseSecurityClassification(
                    "0000000001", "AGM.A", SecurityType.COMMON_STOCK,
                    "MASSIVE", observed_at, "ref-agm-a", "CS",
                ),
            ]
        )

        result = SecurityClassificationService(db, provider).sync()

        assert result.classified == 4
        assert result.unknown == 0
        assert result.unmatched == 0
        assert [s.security_type for s in securities] == [
            SecurityType.PREFERRED_STOCK,
            SecurityType.UNIT,
            SecurityType.WARRANT,
            SecurityType.COMMON_STOCK,
        ]
    finally:
        db.close()
        engine.dispose()


def test_security_classification_does_not_use_ambiguous_symbol_alias():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        company = Company(cik="0000000001", name="Example")
        db.add(company)
        db.flush()
        security = Security(
            company_id=company.id,
            symbol="ABC-A",
            exchange="NYSE",
        )
        db.add(security)
        db.commit()

        observed_at = datetime.now(timezone.utc)
        provider = FakeProvider(
            [
                UniverseSecurityClassification(
                    "0000000001", "ABC.A", SecurityType.COMMON_STOCK,
                    "MASSIVE", observed_at, "ref-1", "CS",
                ),
                UniverseSecurityClassification(
                    "0000000001", "ABCA", SecurityType.COMMON_STOCK,
                    "MASSIVE", observed_at, "ref-2", "CS",
                ),
            ]
        )

        result = SecurityClassificationService(db, provider).sync()

        assert result.classified == 0
        assert result.unmatched == 1
        assert security.security_type is SecurityType.UNKNOWN
    finally:
        db.close()
        engine.dispose()


def test_security_classification_records_type_transition_as_bitemporal_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        company = Company(cik="0000320193", name="Apple Inc.")
        db.add(company)
        db.flush()
        security = Security(
            company_id=company.id,
            symbol="AAPL",
            exchange="NASDAQ",
            security_type=SecurityType.UNKNOWN,
        )
        db.add(security)
        db.commit()

        first = datetime(2026, 1, 2, tzinfo=timezone.utc)
        second = datetime(2026, 3, 2, tzinfo=timezone.utc)
        provider = FakeProvider([
            UniverseSecurityClassification(
                "0000320193", "AAPL", SecurityType.COMMON_STOCK,
                "MASSIVE", first, "ref-common", "CS",
            )
        ])
        SecurityClassificationService(db, provider).sync()

        provider.rows = [
            UniverseSecurityClassification(
                "0000320193", "AAPL", SecurityType.ADR,
                "MASSIVE", second, "ref-adr", "ADR",
            )
        ]
        SecurityClassificationService(db, provider).sync()

        rows = db.query(SecurityClassificationHistory).order_by(
            SecurityClassificationHistory.known_at
        ).all()
        assert len(rows) == 3
        assert rows[0].security_type is SecurityType.COMMON_STOCK
        assert rows[0].effective_to is None
        assert rows[0].is_current is False
        assert rows[1].security_type is SecurityType.COMMON_STOCK
        assert rows[1].effective_to == second.date()
        assert rows[1].known_at.replace(tzinfo=timezone.utc) == second
        assert rows[2].security_type is SecurityType.ADR
        assert rows[2].effective_from == second.date()
        assert rows[2].is_current is True
    finally:
        db.close()
        engine.dispose()
