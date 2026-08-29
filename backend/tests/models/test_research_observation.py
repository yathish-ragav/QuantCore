from datetime import datetime, timezone

from quantcore.models.research_observation import ResearchObservation


def test_research_observation_has_expected_table_contract():
    table = ResearchObservation.__table__

    assert table.name == "research_observations"
    assert {column.name for column in table.columns} == {
        "id",
        "security_id",
        "as_of",
        "observation_key",
        "definition_version",
        "value_numeric",
        "value_text",
        "unit",
        "input_manifest",
        "input_fingerprint",
        "created_at",
    }


def test_research_observation_identity_is_unique():
    constraints = ResearchObservation.__table__.constraints
    identity = next(
        constraint
        for constraint in constraints
        if constraint.name == "uq_research_observation_identity"
    )

    assert [column.name for column in identity.columns] == [
        "security_id",
        "as_of",
        "observation_key",
        "definition_version",
    ]
