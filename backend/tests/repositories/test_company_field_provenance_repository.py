from datetime import datetime, timezone
from unittest.mock import Mock

from quantcore.models.provenance import (
    CompanyField,
    CompanyFieldProvenance,
    DataSource,
)
from quantcore.repositories.company_field_provenance_repository import (
    CompanyFieldProvenanceRepository,
)


def make_repository():
    db = Mock()
    return CompanyFieldProvenanceRepository(db), db


def test_get_returns_existing_provenance():

    repository, db = make_repository()
    provenance = Mock()
    db.scalar.return_value = provenance

    result = repository.get(
        1,
        CompanyField.NAME,
    )

    assert result is provenance
    db.scalar.assert_called_once()


def test_get_returns_none_when_missing():

    repository, db = make_repository()
    db.scalar.return_value = None

    result = repository.get(
        1,
        CompanyField.NAME,
    )

    assert result is None


def test_upsert_creates_new_provenance():

    repository, db = make_repository()
    db.scalar.return_value = None

    fetched_at = datetime.now(timezone.utc)

    result = repository.upsert(
        company_id=1,
        field_name=CompanyField.NAME,
        source=DataSource.SEC,
        fetched_at=fetched_at,
    )

    assert isinstance(result, CompanyFieldProvenance)
    assert result.company_id == 1
    assert result.field_name == CompanyField.NAME
    assert result.source == DataSource.SEC
    assert result.fetched_at == fetched_at
    db.add.assert_called_once_with(result)


def test_upsert_updates_existing_provenance():

    repository, db = make_repository()
    existing = CompanyFieldProvenance(
        company_id=1,
        field_name=CompanyField.NAME,
        source=DataSource.YAHOO,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db.scalar.return_value = existing

    fetched_at = datetime.now(timezone.utc)

    result = repository.upsert(
        company_id=1,
        field_name=CompanyField.NAME,
        source=DataSource.SEC,
        fetched_at=fetched_at,
        source_reference="accession:000000",
    )

    assert result is existing
    assert existing.source == DataSource.SEC
    assert existing.fetched_at == fetched_at
    assert existing.source_reference == "accession:000000"
    db.add.assert_not_called()
