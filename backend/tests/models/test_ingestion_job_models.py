from quantcore.models.ingestion import (
    IngestionJob,
    IngestionJobStatus,
    IngestionRun,
)


def test_ingestion_job_status_and_schema():
    assert IngestionJobStatus.QUEUED.value == "QUEUED"
    columns = IngestionJob.__table__.c
    assert "dataset" in columns
    assert "symbols" in columns
    assert "target_limit" in columns
    assert "idempotency_key" in columns
    assert "request_fingerprint" in columns
    assert "status" in columns
    assert "attempt_count" in columns
    assert "worker_id" in columns
    assert "heartbeat_at" in columns


def test_ingestion_run_can_reference_job_attempt():
    columns = IngestionRun.__table__.c
    assert "job_id" in columns
    assert "attempt_number" in columns
    constraints = IngestionRun.__table__.constraints
    assert any(
        getattr(constraint, "name", None) == "uq_ingestion_run_job_attempt"
        for constraint in constraints
    )
