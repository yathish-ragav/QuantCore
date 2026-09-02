from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)
from quantcore.services.research_factor_panel_service import (
    ResearchFactorPanel,
    ResearchFactorPanelRow,
)


AS_OF_1 = datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc)
AS_OF_2 = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)


def row(symbol, security_id, as_of, value):
    factor = ResearchFactorValue(
        factor_key="quality_score",
        definition_version="1",
        symbol=symbol,
        security_id=security_id,
        as_of=as_of,
        value_numeric=value,
        unit="score",
        input_manifest={"source": "test"},
    )
    return ResearchFactorPanelRow(
        symbol=symbol,
        security_id=security_id,
        as_of=as_of,
        factor_value=factor,
    )


def panel(*rows):
    return ResearchFactorPanel(
        factor_key="quality_score",
        definition_version="1",
        rows=tuple(rows),
        unit="score",
    )


def test_rank_factor_panel_ranks_independently_per_cross_section():
    result = ResearchFactorCrossSectionalService().rank_factor_panel(
        panel(
            row("MSFT", 20, AS_OF_2, 0.2),
            row("AAPL", 10, AS_OF_1, 0.5),
            row("NVDA", 30, AS_OF_2, 0.8),
            row("AAPL", 10, AS_OF_2, 0.4),
            row("MSFT", 20, AS_OF_1, 0.2),
        )
    )

    assert isinstance(result, ResearchFactorRankedPanel)
    assert (result.factor_key, result.definition_version) == ("quality_score", "1")
    assert result.ranking == "average_tie"
    assert result.higher_is_better is True
    assert [(r.symbol, r.as_of, r.rank, r.normalized_rank) for r in result.rows] == [
        ("AAPL", AS_OF_1, 1.0, 1.0),
        ("MSFT", AS_OF_1, 2.0, 0.0),
        ("NVDA", AS_OF_2, 1.0, 1.0),
        ("AAPL", AS_OF_2, 2.0, 0.5),
        ("MSFT", AS_OF_2, 3.0, 0.0),
    ]
    assert result.rows[0].factor_value.input_manifest == {"source": "test"}


def test_rank_factor_panel_uses_average_ranks_for_ties():
    result = ResearchFactorCrossSectionalService().rank_factor_panel(
        panel(
            row("AAPL", 10, AS_OF_1, 0.5),
            row("MSFT", 20, AS_OF_1, 0.5),
            row("NVDA", 30, AS_OF_1, 0.1),
            row("META", 40, AS_OF_1, 0.9),
        )
    )

    assert [(r.symbol, r.rank, r.normalized_rank) for r in result.rows] == [
        ("META", 1.0, 1.0),
        ("AAPL", 2.5, 0.5),
        ("MSFT", 2.5, 0.5),
        ("NVDA", 4.0, 0.0),
    ]


def test_rank_factor_panel_can_treat_lower_values_as_better():
    result = ResearchFactorCrossSectionalService().rank_factor_panel(
        panel(
            row("AAPL", 10, AS_OF_1, 0.5),
            row("MSFT", 20, AS_OF_1, 0.1),
            row("NVDA", 30, AS_OF_1, 0.9),
        ),
        higher_is_better=False,
    )

    assert [(r.symbol, r.rank, r.normalized_rank) for r in result.rows] == [
        ("MSFT", 1.0, 1.0),
        ("AAPL", 2.0, 0.5),
        ("NVDA", 3.0, 0.0),
    ]


def test_rank_factor_panel_singleton_cross_section_gets_neutral_normalized_rank():
    result = ResearchFactorCrossSectionalService().rank_factor_panel(
        panel(row("AAPL", 10, AS_OF_1, 0.5))
    )

    assert result.rows[0].rank == 1.0
    assert result.rows[0].normalized_rank == 0.5


def test_rank_factor_panel_rejects_text_factor_values():
    factor = ResearchFactorValue(
        factor_key="quality_label",
        definition_version="1",
        symbol="AAPL",
        security_id=10,
        as_of=AS_OF_1,
        value_text="strong",
        unit=None,
    )
    text_row = ResearchFactorPanelRow("AAPL", 10, AS_OF_1, factor)
    text_panel = ResearchFactorPanel("quality_label", "1", (text_row,), None)

    with pytest.raises(InvalidInputError):
        ResearchFactorCrossSectionalService().rank_factor_panel(text_panel)


def test_rank_factor_panel_rejects_duplicate_security_as_of_points():
    duplicate = row("AAPL", 10, AS_OF_1, 0.5)
    with pytest.raises(InvalidInputError):
        ResearchFactorCrossSectionalService().rank_factor_panel(
            panel(duplicate, duplicate)
        )


def test_rank_factor_panel_rejects_non_boolean_direction():
    with pytest.raises(InvalidInputError):
        ResearchFactorCrossSectionalService().rank_factor_panel(
            panel(row("AAPL", 10, AS_OF_1, 0.5)), higher_is_better=1
        )


def test_rank_factor_panel_rejects_non_finite_values():
    with pytest.raises(InvalidInputError):
        ResearchFactorCrossSectionalService().rank_factor_panel(
            panel(row("AAPL", 10, AS_OF_1, float("nan")))
        )


def test_rank_factor_panel_rejects_empty_panel():
    empty = ResearchFactorPanel("quality_score", "1", (), "score")
    with pytest.raises(InvalidInputError):
        ResearchFactorCrossSectionalService().rank_factor_panel(empty)


def test_rank_factor_panel_preserves_deterministic_output_type():
    result = ResearchFactorCrossSectionalService().rank_factor_panel(
        panel(row("AAPL", 10, AS_OF_1, 0.5))
    )
    assert all(isinstance(item, ResearchFactorRankRow) for item in result.rows)
