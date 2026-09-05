from quantcore.ingestion.datasets import IngestionDataset, IngestionScope
from quantcore.models.ingestion_lineage import IngestionLineage
from quantcore.models.provenance import DataSource


def test_ingestion_lineage_has_execution_and_entity_identity():
    columns = IngestionLineage.__table__.c
    assert columns.ingestion_run_id.foreign_keys
    assert columns.company_id.foreign_keys
    assert columns.security_id.foreign_keys
    assert columns.dataset is not None
    assert columns.scope is not None
    assert columns.source is not None
    assert columns.records_processed is not None
    assert columns.recorded_at is not None

    constraints = IngestionLineage.__table__.constraints
    assert any(
        c.name == "uq_ingestion_lineage_run_entity"
        for c in constraints
    )
    assert any(
        c.name == "ck_ingestion_lineage_scope_entity"
        for c in constraints
    )
    assert any(
        c.name == "ck_ingestion_lineage_records_nonnegative"
        for c in constraints
    )


def test_lineage_uses_existing_dataset_scope_and_source_contracts():
    assert IngestionDataset.PRICE_HISTORY.value == "price_history"
    assert IngestionScope.SECURITY.value == "security"
    assert DataSource.YAHOO.value == "YAHOO"
