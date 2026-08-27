from quantcore.models.macro_ingestion import MacroIngestionState


def test_macro_ingestion_state_has_source_series_identity():
    table = MacroIngestionState.__table__
    constraint = next(
        item for item in table.constraints
        if getattr(item, "name", None) == "uq_macro_ingestion_state_source_series"
    )
    assert [column.name for column in constraint.columns] == ["source", "series_id"]
