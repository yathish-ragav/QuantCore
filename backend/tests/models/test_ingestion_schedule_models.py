from quantcore.models.ingestion_schedule import IngestionSchedule


def test_ingestion_schedule_schema():
    columns = IngestionSchedule.__table__.c
    for name in (
        "name",
        "dataset",
        "symbols",
        "target_limit",
        "only_stale",
        "interval_seconds",
        "next_run_at",
        "enabled",
        "last_triggered_at",
    ):
        assert name in columns

    constraints = IngestionSchedule.__table__.constraints
    names = {getattr(constraint, "name", None) for constraint in constraints}
    assert "uq_ingestion_schedule_name" in names
    assert "ck_ingestion_schedule_interval_positive" in names
    assert "ck_ingestion_schedule_limit_positive" in names


def test_ingestion_schedule_has_due_polling_index():
    indexes = {
        index.name: tuple(index.columns.keys())
        for index in IngestionSchedule.__table__.indexes
    }
    assert indexes["ix_ingestion_schedules_enabled_next_run_at_id"] == (
        "enabled",
        "next_run_at",
        "id",
    )
