from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)
from quantcore.services.research_signal_service import (
    ResearchSignalDefinition,
    ResearchSignalService,
)


AS_OF = datetime(2026, 8, 20, 16, tzinfo=timezone.utc)


def ranked_panel(factor_key: str, version: str, rows: list[tuple[int, str, float]]) -> ResearchFactorRankedPanel:
    return ResearchFactorRankedPanel(
        factor_key=factor_key,
        definition_version=version,
        ranking="average_tie",
        higher_is_better=True,
        rows=tuple(
            ResearchFactorRankRow(
                symbol=symbol,
                security_id=security_id,
                as_of=AS_OF,
                factor_value=ResearchFactorValue(
                    factor_key=factor_key,
                    definition_version=version,
                    symbol=symbol,
                    security_id=security_id,
                    as_of=AS_OF,
                    value_numeric=value,
                ),
                rank=index + 1,
                normalized_rank=normalized_rank,
            )
            for index, (security_id, symbol, normalized_rank) in enumerate(rows)
            for value in [float(normalized_rank)]
        ),
    )


def definition(weights=(0.5, 0.5)):
    return ResearchSignalDefinition(
        signal_key="quality_momentum",
        definition_version="1",
        factor_identities=(("quality", "1"), ("momentum", "1")),
        weights=weights,
    )


def panels():
    return {
        ("quality", "1"): ranked_panel(
            "quality", "1", [(1, "AAA", 1.0), (2, "BBB", 0.0)]
        ),
        ("momentum", "1"): ranked_panel(
            "momentum", "1", [(1, "AAA", 0.5), (2, "BBB", 0.5)]
        ),
    }


def test_constructs_weighted_composite_signal():
    result = ResearchSignalService().construct_signal(definition(), panels())
    assert [row.score for row in result.rows] == pytest.approx([0.75, 0.25])
    assert [row.centered_score for row in result.rows] == pytest.approx([0.5, -0.5])


def test_preserves_factor_contributions_and_provenance():
    result = ResearchSignalService().construct_signal(definition(), panels())
    contributions = result.rows[0].contributions
    assert [(c.factor_key, c.definition_version) for c in contributions] == [
        ("quality", "1"),
        ("momentum", "1"),
    ]
    assert [c.weighted_contribution for c in contributions] == pytest.approx([0.5, 0.25])


def test_signal_identity_and_construction_are_explicit():
    result = ResearchSignalService().construct_signal(definition(), panels())
    assert result.signal_key == "quality_momentum"
    assert result.definition_version == "1"
    assert result.construction == "WEIGHTED_NORMALIZED_RANK_AVERAGE"


def test_accepts_single_factor_signal():
    panel = ranked_panel("quality", "1", [(1, "AAA", 0.8), (2, "BBB", 0.2)])
    single = ResearchSignalDefinition(
        signal_key="quality_signal",
        definition_version="1",
        factor_identities=(("quality", "1"),),
        weights=(1.0,),
    )
    result = ResearchSignalService().construct_signal(single, {("quality", "1"): panel})
    assert [row.score for row in result.rows] == pytest.approx([0.8, 0.2])


def test_rejects_weights_that_do_not_sum_to_one():
    with pytest.raises(InvalidInputError):
        ResearchSignalDefinition(
            signal_key="x",
            definition_version="1",
            factor_identities=(("quality", "1"),),
            weights=(0.5,),
        )


def test_rejects_non_positive_weights():
    with pytest.raises(InvalidInputError):
        ResearchSignalDefinition(
            signal_key="x",
            definition_version="1",
            factor_identities=(("quality", "1"),),
            weights=(0.0,),
        )


def test_rejects_duplicate_factor_identities():
    with pytest.raises(InvalidInputError):
        ResearchSignalDefinition(
            signal_key="x",
            definition_version="1",
            factor_identities=(("quality", "1"), ("quality", "1")),
            weights=(0.5, 0.5),
        )


def test_rejects_missing_factor_panel():
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), {(
            "quality", "1"
        ): panels()[("quality", "1")]})


def test_rejects_extra_factor_panel():
    supplied = panels()
    supplied[("value", "1")] = ranked_panel("value", "1", [(1, "AAA", 0.5), (2, "BBB", 0.5)])
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), supplied)


def test_rejects_mismatched_security_universe():
    supplied = panels()
    supplied[("momentum", "1")] = ranked_panel(
        "momentum", "1", [(1, "AAA", 0.5), (3, "CCC", 0.5)]
    )
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), supplied)


def test_rejects_duplicate_security_as_of_in_input():
    panel = ranked_panel("quality", "1", [(1, "AAA", 1.0), (2, "BBB", 0.0)])
    duplicate = ResearchFactorRankRow(
        symbol="AAA",
        security_id=1,
        as_of=AS_OF,
        factor_value=panel.rows[0].factor_value,
        rank=1,
        normalized_rank=1.0,
    )
    bad = ResearchFactorRankedPanel(
        factor_key=panel.factor_key,
        definition_version=panel.definition_version,
        ranking=panel.ranking,
        higher_is_better=panel.higher_is_better,
        rows=panel.rows + (duplicate,),
    )
    supplied = panels()
    supplied[("quality", "1")] = bad
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), supplied)


def test_rejects_normalized_rank_outside_unit_interval():
    supplied = panels()
    row = supplied[("quality", "1")].rows[0]
    bad_row = ResearchFactorRankRow(
        symbol=row.symbol,
        security_id=row.security_id,
        as_of=row.as_of,
        factor_value=row.factor_value,
        rank=row.rank,
        normalized_rank=1.5,
    )
    bad_panel = ResearchFactorRankedPanel(
        factor_key="quality",
        definition_version="1",
        ranking="average_tie",
        higher_is_better=True,
        rows=(bad_row, supplied[("quality", "1")].rows[1]),
    )
    supplied[("quality", "1")] = bad_panel
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), supplied)


def test_is_deterministically_ordered_by_as_of_then_security():
    p1 = ranked_panel("quality", "1", [(2, "BBB", 0.0), (1, "AAA", 1.0)])
    p2 = ranked_panel("momentum", "1", [(2, "BBB", 0.5), (1, "AAA", 0.5)])
    result = ResearchSignalService().construct_signal(
        definition(), {("quality", "1"): p1, ("momentum", "1"): p2}
    )
    assert [(r.as_of, r.security_id) for r in result.rows] == [
        (AS_OF, 1),
        (AS_OF, 2),
    ]


def test_score_is_bounded_for_valid_weights_and_ranks():
    result = ResearchSignalService().construct_signal(definition(), panels())
    assert all(0.0 <= row.score <= 1.0 for row in result.rows)
    assert all(-1.0 <= row.centered_score <= 1.0 for row in result.rows)


def test_rejects_panel_identity_mismatch():
    supplied = panels()
    wrong_key = ranked_panel("other", "1", [(1, "AAA", 1.0), (2, "BBB", 0.0)])
    supplied[("quality", "1")] = wrong_key
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), supplied)


def test_rejects_factor_value_identity_mismatch():
    supplied = panels()
    row = supplied[("quality", "1")].rows[0]
    bad_value = ResearchFactorValue(
        factor_key="other",
        definition_version="1",
        symbol=row.symbol,
        security_id=row.security_id,
        as_of=row.as_of,
        value_numeric=row.factor_value.value_numeric,
    )
    bad_row = ResearchFactorRankRow(
        symbol=row.symbol,
        security_id=row.security_id,
        as_of=row.as_of,
        factor_value=bad_value,
        rank=row.rank,
        normalized_rank=row.normalized_rank,
    )
    supplied[("quality", "1")] = ResearchFactorRankedPanel(
        factor_key="quality",
        definition_version="1",
        ranking="average_tie",
        higher_is_better=True,
        rows=(bad_row, supplied[("quality", "1")].rows[1]),
    )
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), supplied)


def test_rejects_factor_value_timestamp_mismatch():
    supplied = panels()
    row = supplied[("quality", "1")].rows[0]
    bad_value = ResearchFactorValue(
        factor_key="quality",
        definition_version="1",
        symbol=row.symbol,
        security_id=row.security_id,
        as_of=AS_OF.replace(day=21),
        value_numeric=row.factor_value.value_numeric,
    )
    bad_row = ResearchFactorRankRow(
        symbol=row.symbol,
        security_id=row.security_id,
        as_of=row.as_of,
        factor_value=bad_value,
        rank=row.rank,
        normalized_rank=row.normalized_rank,
    )
    supplied[("quality", "1")] = ResearchFactorRankedPanel(
        factor_key="quality",
        definition_version="1",
        ranking="average_tie",
        higher_is_better=True,
        rows=(bad_row, supplied[("quality", "1")].rows[1]),
    )
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), supplied)


def test_rejects_non_finite_factor_rank():
    supplied = panels()
    row = supplied[("quality", "1")].rows[0]
    bad_row = ResearchFactorRankRow(
        symbol=row.symbol,
        security_id=row.security_id,
        as_of=row.as_of,
        factor_value=row.factor_value,
        rank=float("nan"),
        normalized_rank=row.normalized_rank,
    )
    supplied[("quality", "1")] = ResearchFactorRankedPanel(
        factor_key="quality",
        definition_version="1",
        ranking="average_tie",
        higher_is_better=True,
        rows=(bad_row, supplied[("quality", "1")].rows[1]),
    )
    with pytest.raises(InvalidInputError):
        ResearchSignalService().construct_signal(definition(), supplied)
