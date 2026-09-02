from datetime import datetime, timezone

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorRankedPanel,
    ResearchFactorRankRow,
)
from quantcore.services.research_factor_evaluation_service import (
    ResearchFactorEvaluation,
    ResearchFactorEvaluationService,
)


AS_OF_1 = datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc)
AS_OF_2 = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)


def row(symbol, security_id, as_of, value, rank, normalized_rank):
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
    return ResearchFactorRankRow(
        symbol=symbol,
        security_id=security_id,
        as_of=as_of,
        factor_value=factor,
        rank=rank,
        normalized_rank=normalized_rank,
    )


def panel(*rows):
    return ResearchFactorRankedPanel(
        factor_key="quality_score",
        definition_version="1",
        rows=tuple(rows),
        ranking="average_tie",
        higher_is_better=True,
    )


def test_evaluate_ranked_panel_produces_per_cross_section_diagnostics():
    result = ResearchFactorEvaluationService().evaluate_ranked_panel(
        panel(
            row("AAPL", 10, AS_OF_1, 0.5, 1.0, 1.0),
            row("MSFT", 20, AS_OF_1, 0.2, 2.0, 0.0),
            row("NVDA", 30, AS_OF_2, 0.8, 1.0, 1.0),
            row("AAPL", 10, AS_OF_2, 0.4, 2.0, 0.5),
            row("MSFT", 20, AS_OF_2, 0.2, 3.0, 0.0),
        )
    )

    assert isinstance(result, ResearchFactorEvaluation)
    assert (result.factor_key, result.definition_version) == ("quality_score", "1")
    assert result.cross_section_count == 2
    assert result.total_observation_count == 5
    assert result.minimum_cross_section_size == 2
    assert result.maximum_cross_section_size == 3
    assert result.mean_cross_section_size == 2.5
    assert result.mean_cross_section_value == pytest.approx((0.35 + (0.8 + 0.4 + 0.2) / 3) / 2)
    assert result.mean_cross_section_stddev == pytest.approx((0.15 + 0.24944382578492943) / 2)
    assert result.mean_cross_section_range == pytest.approx((0.3 + 0.6) / 2)

    first, second = result.cross_sections
    assert first.as_of == AS_OF_1
    assert first.observation_count == 2
    assert first.mean_value == pytest.approx(0.35)
    assert first.median_value == pytest.approx(0.35)
    assert first.stddev_value == pytest.approx(0.15)
    assert first.minimum_value == pytest.approx(0.2)
    assert first.maximum_value == pytest.approx(0.5)
    assert first.range_value == pytest.approx(0.3)

    assert second.as_of == AS_OF_2
    assert second.observation_count == 3
    assert second.median_value == pytest.approx(0.4)
    assert second.range_value == pytest.approx(0.6)


def test_evaluate_ranked_panel_uses_population_standard_deviation():
    result = ResearchFactorEvaluationService().evaluate_ranked_panel(
        panel(
            row("AAPL", 10, AS_OF_1, 1.0, 1.0, 1.0),
            row("MSFT", 20, AS_OF_1, 3.0, 2.0, 0.0),
        )
    )
    assert result.cross_sections[0].stddev_value == pytest.approx(1.0)


def test_evaluate_ranked_panel_singleton_has_zero_dispersion():
    result = ResearchFactorEvaluationService().evaluate_ranked_panel(
        panel(row("AAPL", 10, AS_OF_1, 0.5, 1.0, 0.5))
    )
    section = result.cross_sections[0]
    assert section.observation_count == 1
    assert section.mean_value == section.median_value == 0.5
    assert section.stddev_value == 0.0
    assert section.range_value == 0.0


def test_evaluate_ranked_panel_does_not_mix_as_of_values_for_statistics():
    result = ResearchFactorEvaluationService().evaluate_ranked_panel(
        panel(
            row("AAPL", 10, AS_OF_1, 100.0, 1.0, 1.0),
            row("MSFT", 20, AS_OF_1, 101.0, 2.0, 0.0),
            row("AAPL", 10, AS_OF_2, 1.0, 1.0, 1.0),
            row("MSFT", 20, AS_OF_2, 2.0, 2.0, 0.0),
        )
    )
    assert [section.mean_value for section in result.cross_sections] == [100.5, 1.5]
    assert result.mean_cross_section_value == pytest.approx(51.0)


def test_evaluate_ranked_panel_rejects_empty_panel():
    empty = ResearchFactorRankedPanel("quality_score", "1", (), "average_tie", True)
    with pytest.raises(InvalidInputError):
        ResearchFactorEvaluationService().evaluate_ranked_panel(empty)




def test_evaluate_ranked_panel_output_is_deterministic_for_input_order():
    rows = (
        row("AAPL", 10, AS_OF_2, 0.4, 2.0, 0.5),
        row("MSFT", 20, AS_OF_1, 0.2, 2.0, 0.0),
        row("NVDA", 30, AS_OF_2, 0.8, 1.0, 1.0),
        row("AAPL", 10, AS_OF_1, 0.5, 1.0, 1.0),
        row("MSFT", 20, AS_OF_2, 0.2, 3.0, 0.0),
    )
    service = ResearchFactorEvaluationService()
    first = service.evaluate_ranked_panel(panel(*rows))
    second = service.evaluate_ranked_panel(panel(*reversed(rows)))
    assert first == second


def test_evaluate_ranked_panel_rejects_text_factor_values():
    factor = ResearchFactorValue(
        factor_key="quality_score",
        definition_version="1",
        symbol="AAPL",
        security_id=10,
        as_of=AS_OF_1,
        value_text="strong",
        unit=None,
    )
    ranked = ResearchFactorRankRow("AAPL", 10, AS_OF_1, factor, 1.0, 1.0)
    with pytest.raises(InvalidInputError):
        ResearchFactorEvaluationService().evaluate_ranked_panel(
            ResearchFactorRankedPanel("quality_score", "1", (ranked,), "average_tie", True)
        )


def test_evaluate_ranked_panel_rejects_identity_mismatch():
    factor = ResearchFactorValue(
        factor_key="other_factor",
        definition_version="1",
        symbol="AAPL",
        security_id=10,
        as_of=AS_OF_1,
        value_numeric=0.5,
        unit="score",
    )
    ranked = ResearchFactorRankRow("AAPL", 10, AS_OF_1, factor, 1.0, 1.0)
    with pytest.raises(InvalidInputError):
        ResearchFactorEvaluationService().evaluate_ranked_panel(
            ResearchFactorRankedPanel("quality_score", "1", (ranked,), "average_tie", True)
        )




def test_evaluate_ranked_panel_rejects_symbol_mismatch():
    factor = ResearchFactorValue(
        factor_key="quality_score",
        definition_version="1",
        symbol="MSFT",
        security_id=10,
        as_of=AS_OF_1,
        value_numeric=0.5,
        unit="score",
    )
    ranked = ResearchFactorRankRow("AAPL", 10, AS_OF_1, factor, 1.0, 1.0)
    with pytest.raises(InvalidInputError):
        ResearchFactorEvaluationService().evaluate_ranked_panel(
            ResearchFactorRankedPanel("quality_score", "1", (ranked,), "average_tie", True)
        )


def test_evaluate_ranked_panel_rejects_invalid_normalized_rank():
    with pytest.raises(InvalidInputError):
        ResearchFactorEvaluationService().evaluate_ranked_panel(
            panel(row("AAPL", 10, AS_OF_1, 0.5, 1.0, 1.1))
        )


def test_evaluate_ranked_panel_rejects_duplicate_security_as_of_points():
    duplicate = row("AAPL", 10, AS_OF_1, 0.5, 1.0, 1.0)
    with pytest.raises(InvalidInputError):
        ResearchFactorEvaluationService().evaluate_ranked_panel(
            panel(duplicate, duplicate)
        )
