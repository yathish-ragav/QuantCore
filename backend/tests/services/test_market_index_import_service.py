from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from quantcore.models.market_index_load import MarketIndexDataLoadStatus
from quantcore.services.market_index_import_service import (
    IndexMembershipImportRow,
    MarketIndexImportService,
)


def test_fingerprint_is_order_independent():
    rows = [
        IndexMembershipImportRow(2, date(2020, 1, 1), None, Decimal("0.2"), datetime(2020, 1, 2, tzinfo=timezone.utc)),
        IndexMembershipImportRow(1, date(2020, 1, 1), None, Decimal("0.8"), datetime(2020, 1, 2, tzinfo=timezone.utc)),
    ]
    first = MarketIndexImportService._fingerprint(tuple(rows))
    second = MarketIndexImportService._fingerprint(tuple(reversed(rows)))
    assert first == second


def test_import_rows_requires_authorized_source_and_matching_index_source():
    service = MarketIndexImportService.__new__(MarketIndexImportService)
    service.db = Mock()
    service.index_service = Mock()
    service.source_service = Mock()
    service.load_repository = Mock()

    source = Mock(id=7, key="SPDJI")
    service.source_service.require_storage_authorized.return_value = source
    index = Mock(id=3, key="SP500", data_source_id=8)
    service.index_service.get.return_value = index

    import pytest
    from quantcore.core.exceptions import DataValidationError

    with pytest.raises(DataValidationError, match="not configured"):
        service.import_rows(
            index_key="SP500",
            source_key="SPDJI",
            rows=[
                IndexMembershipImportRow(
                    1, date(2020, 1, 1), None, None,
                    datetime(2020, 1, 2, tzinfo=timezone.utc),
                )
            ],
        )


def test_import_rows_is_idempotent_for_completed_fingerprint():
    service = MarketIndexImportService.__new__(MarketIndexImportService)
    service.db = Mock()
    service.index_service = Mock()
    service.source_service = Mock()
    service.load_repository = Mock()

    source = Mock(id=7, key="SPDJI")
    index = Mock(id=3, key="SP500", data_source_id=7)
    completed = Mock(status=MarketIndexDataLoadStatus.COMPLETED, records_imported=5)
    service.source_service.require_storage_authorized.return_value = source
    service.index_service.get.return_value = index
    service.load_repository.get_by_fingerprint.return_value = completed

    result = service.import_rows(
        index_key="SP500",
        source_key="SPDJI",
        rows=[
            IndexMembershipImportRow(
                1, date(2020, 1, 1), None, None,
                datetime(2020, 1, 2, tzinfo=timezone.utc),
            )
        ],
    )

    assert result == 5
    service.index_service.add_constituents.assert_not_called()


def test_import_rows_persists_authorized_membership_and_load_audit():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from quantcore.db.database import Base
    from quantcore.models.company import Company
    from quantcore.models.market_index import MarketIndex, MarketIndexConstituent
    from quantcore.models.market_index_load import MarketIndexDataLoad
    from quantcore.models.market_index_source import MarketIndexDataSource
    from quantcore.models.security import Security

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Company.__table__,
            Security.__table__,
            MarketIndexDataSource.__table__,
            MarketIndex.__table__,
            MarketIndexConstituent.__table__,
            MarketIndexDataLoad.__table__,
        ],
    )
    session = Session(engine)
    try:
        company = Company(
            cik="0000000004", name="Example", sector="", industry="", country="", website=""
        )
        session.add(company)
        session.flush()
        security = Security(company_id=company.id, symbol="TEST", exchange="NASDAQ")
        session.add(security)
        session.flush()
        source = MarketIndexDataSource(
            key="LICENSED_TEST",
            provider="Test Provider",
            dataset="Historical Constituents",
            authority="AUTHORITATIVE",
            license_status="AUTHORIZED",
            storage_allowed=True,
        )
        session.add(source)
        session.flush()
        index = MarketIndex(
            key="TESTIDX", name="Test Index", provider="Test Provider", data_source_id=source.id
        )
        session.add(index)
        session.commit()

        service = MarketIndexImportService(session)
        rows = [
            IndexMembershipImportRow(
                security_id=security.id,
                effective_from=date(2020, 1, 1),
                effective_to=None,
                weight=Decimal("1"),
                known_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
                source_reference="licensed-file-2020",
            )
        ]
        assert service.import_rows(index_key="TESTIDX", source_key="LICENSED_TEST", rows=rows) == 1
        assert service.import_rows(index_key="TESTIDX", source_key="LICENSED_TEST", rows=rows) == 1
        assert session.query(MarketIndexConstituent).count() == 1
        assert session.query(MarketIndexDataLoad).count() == 1
    finally:
        session.close()
        engine.dispose()
