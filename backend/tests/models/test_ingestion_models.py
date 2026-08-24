from quantcore.ingestion.datasets import (
    DATASET_POLICIES,
    DATASET_SCOPES,
    IngestionDataset,
    IngestionScope,
)
from quantcore.models.ingestion import (
    IngestionRun,
    IngestionRunStatus,
    IngestionState,
)


def test_ingestion_datasets_have_explicit_scope_and_policy():
    assert set(DATASET_SCOPES) == set(IngestionDataset)
    assert set(DATASET_POLICIES) == set(IngestionDataset)
    assert DATASET_SCOPES[IngestionDataset.PRICE_HISTORY] is IngestionScope.SECURITY
    assert DATASET_SCOPES[IngestionDataset.BALANCE_SHEET] is IngestionScope.COMPANY


def test_ingestion_state_has_explicit_entity_foreign_keys():
    columns = IngestionState.__table__.c
    assert columns.company_id.foreign_keys
    assert columns.security_id.foreign_keys

    constraints = IngestionState.__table__.constraints
    assert any(
        c.name == "uq_ingestion_state_dataset_company"
        for c in constraints
    )
    assert any(
        c.name == "uq_ingestion_state_dataset_security"
        for c in constraints
    )


def test_ingestion_run_defaults_to_running():
    assert IngestionRunStatus.RUNNING.value == "RUNNING"
    assert "status" in IngestionRun.__table__.c
    assert "started_at" in IngestionRun.__table__.c
