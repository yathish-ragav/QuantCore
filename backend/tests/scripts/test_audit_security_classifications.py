from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quantcore.core.enums import SecurityType
from quantcore.db.database import Base
from quantcore.models.company import Company
from quantcore.models.security import Security, SecurityStatus
from quantcore.universe.models import UniverseSecurityClassification
from quantcore.universe.audit import audit


class FakeProvider:
    def __init__(self, rows):
        self.rows = rows

    def fetch(self):
        return self.rows


def test_audit_distinguishes_unknown_and_unmatched_reconciliation_cases():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        companies = [
            Company(cik="0000000001", name="Known"),
            Company(cik="0000000002", name="Unknown Type"),
            Company(cik="0000000003", name="CIK Match"),
            Company(cik="0000000004", name="Symbol Match"),
            Company(cik="0000000005", name="Absent"),
        ]
        db.add_all(companies)
        db.flush()
        db.add_all([
            Security(company_id=companies[0].id, symbol="KNOWN", exchange="NASDAQ", status=SecurityStatus.ACTIVE),
            Security(company_id=companies[1].id, symbol="UNK", exchange="NYSE", status=SecurityStatus.ACTIVE),
            Security(company_id=companies[2].id, symbol="OLD", exchange="NYSE", status=SecurityStatus.ACTIVE),
            Security(company_id=companies[3].id, symbol="SAME", exchange="NYSE", status=SecurityStatus.ACTIVE),
            Security(company_id=companies[4].id, symbol="ABSENT", exchange="NYSE", status=SecurityStatus.ACTIVE),
        ])
        db.commit()

        observed = datetime.now(timezone.utc)
        provider = FakeProvider([
            UniverseSecurityClassification("0000000001", "KNOWN", SecurityType.COMMON_STOCK, "MASSIVE", observed, "ref", "CS"),
            UniverseSecurityClassification("0000000002", "UNK", SecurityType.UNKNOWN, "MASSIVE", observed, "ref", "FUTURE_CODE"),
            UniverseSecurityClassification("0000000003", "NEW", SecurityType.COMMON_STOCK, "MASSIVE", observed, "ref", "CS"),
            UniverseSecurityClassification("0000000099", "SAME", SecurityType.COMMON_STOCK, "MASSIVE", observed, "ref", "CS"),
        ])

        report = audit(db, provider)

        assert report["summary"] == {
            "classified": 1,
            "unknown": 1,
            "unmatched": 3,
            "classified_plus_unknown_plus_unmatched": 5,
        }
        assert report["unknown"]["by_provider_type"] == {"FUTURE_CODE": 1}
        assert report["unmatched"]["by_reason"] == {
            "CIK_PRESENT_DIFFERENT_SYMBOL": 1,
            "SYMBOL_PRESENT_DIFFERENT_CIK": 1,
            "NEITHER_CIK_NOR_SYMBOL_PRESENT": 1,
        }
    finally:
        db.close()
        engine.dispose()



def test_audit_reports_safe_symbol_alias_reconciliation():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        company = Company(cik="0000000001", name="Example")
        db.add(company)
        db.flush()
        db.add(
            Security(
                company_id=company.id,
                symbol="AAC-UN",
                exchange="NYSE",
                status=SecurityStatus.ACTIVE,
            )
        )
        db.commit()

        observed = datetime.now(timezone.utc)
        provider = FakeProvider([
            UniverseSecurityClassification(
                "0000000001",
                "AAC.U",
                SecurityType.UNIT,
                "MASSIVE",
                observed,
                "ref",
                "UNIT",
            )
        ])

        report = audit(db, provider)

        assert report["summary"]["classified"] == 1
        assert report["summary"]["unmatched"] == 0
        assert report["reconciliation"]["alias_resolved_count"] == 1
        assert report["reconciliation"]["alias_resolved"][0]["massive_symbol"] == "AAC.U"
    finally:
        db.close()
        engine.dispose()
