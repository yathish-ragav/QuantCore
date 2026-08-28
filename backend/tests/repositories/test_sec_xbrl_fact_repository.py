from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from quantcore.models.sec_xbrl_fact import SECXBRLFactObservation
from quantcore.repositories.sec_xbrl_fact_repository import SECXBRLFactRepository


def test_get_by_identity():
    db = Mock()
    expected = Mock(spec=SECXBRLFactObservation)
    db.scalar.return_value = expected
    repo = SECXBRLFactRepository(db)

    result = repo.get_by_identity(
        company_id=1,
        accession_number="0000320193-24-000123",
        taxonomy="us-gaap",
        concept="Assets",
        unit="USD",
        period_start=None,
        period_end=date(2024, 9, 28),
        frame="",
        qtrs=0,
        value=Decimal("100"),
    )

    assert result is expected
    db.scalar.assert_called_once()


def test_create():
    db = Mock()
    repo = SECXBRLFactRepository(db)
    observation = repo.create(
        company_id=1,
        accession_number="0000320193-24-000123",
        taxonomy="us-gaap",
        concept="Assets",
        unit="USD",
        value=Decimal("100"),
        period_end=date(2024, 9, 28),
        filed_at=date(2024, 11, 1),
        form="10-K",
    )

    db.add.assert_called_once_with(observation)
    assert isinstance(observation, SECXBRLFactObservation)


def test_get_latest_for_company_as_of_uses_revision_window_query():
    db = Mock()
    db.scalars.return_value.all.return_value = [Mock()]
    repo = SECXBRLFactRepository(db)

    result = repo.get_latest_for_company_as_of(1, date(2025, 1, 1))

    assert len(result) == 1
    db.scalars.assert_called_once()


def test_get_latest_for_company_as_of_timestamp_uses_exact_timestamp_boundary():
    db = Mock()
    db.scalars.return_value.all.return_value = [Mock()]
    repo = SECXBRLFactRepository(db)

    as_of = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
    result = repo.get_latest_for_company_as_of_timestamp(1, as_of)

    assert len(result) == 1
    db.scalars.assert_called_once()
