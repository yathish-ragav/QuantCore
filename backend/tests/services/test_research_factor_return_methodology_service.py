from dataclasses import replace
from datetime import datetime, timezone

import pytest

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
    ResearchFactorPanel,
    ResearchFactorPanelRow,
)
from quantcore.services.research_factor_return_methodology_service import (
    ResearchFactorReturnMethodologyService,
    ResearchFactorReturnSeries,
)
from quantcore.services.research_factor_return_service import (
    ResearchFactorReturnPanel,
    ResearchFactorReturnService,
)


AS_OF = datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc)


class Price:
    def __init__(self, date, close):
        self.date = date
        self.close = close
        self.adjusted_close = close


def factor_row(symbol, security_id, value):
    factor = ResearchFactorValue(
        factor_key="quality_score",
        definition_version="1",
        symbol=symbol,
        security_id=security_id,
        as_of=AS_OF,
        value_numeric=value,
        unit="score",
    )
    return ResearchFactorPanelRow(symbol, security_id, AS_OF, factor)


def return_panel(values, returns):
    ranked = ResearchFactorCrossSectionalService().rank_factor_panel(
        ResearchFactorPanel(
            "quality_score",
            "1",
            tuple(factor_row(symbol, security_id, value) for symbol, security_id, value in values),
            "score",
        )
    )
    prices = {
        security_id: (
            Price(datetime(2026, 8, 20, tzinfo=timezone.utc), 100.0),
            Price(
                datetime(2026, 8, 21, tzinfo=timezone.utc),
                100.0 * (1.0 + returns[security_id]),
            ),
        )
        for _, security_id, _ in values
    }
    return ResearchFactorReturnService().compute_forward_returns(
        ranked,
        prices,
        horizon=1,
        return_price_basis=PriceBasis.UNADJUSTED,
    )


def test_compute_factor_return_series_builds_equal_weighted_quintile_spread():
    panel = return_panel(
        [("A", 1, 5), ("B", 2, 4), ("C", 3, 3), ("D", 4, 2), ("E", 5, 1)],
        {1: .10, 2: .06, 3: .02, 4: -.01, 5: -.05},
    )
    result = ResearchFactorReturnMethodologyService().compute_factor_return_series(panel)

    assert isinstance(result, ResearchFactorReturnSeries)
    assert result.bucket_count == 5
    assert result.weighting == "EQUAL_WEIGHTED"
    assert result.construction == "RANK_ORDERED_BUCKET_LONG_SHORT"
    assert result.long_bucket == 1
    assert result.short_bucket == 5
    section = result.slices[0]
    assert section.status == "AVAILABLE"
    assert section.total_observation_count == 5
    assert section.eligible_observation_count == 5
    assert section.long_return == pytest.approx(.10)
    assert section.short_return == pytest.approx(-.05)
    assert section.long_short_return == pytest.approx(.15)
    assert [bucket.observation_count for bucket in section.buckets] == [1, 1, 1, 1, 1]
    assert [bucket.eligible_return_count for bucket in section.buckets] == [1, 1, 1, 1, 1]


def test_bucket_membership_is_based_on_factor_rank_before_return_availability():
    panel = return_panel(
        [("A", 1, 5), ("B", 2, 4), ("C", 3, 3), ("D", 4, 2), ("E", 5, 1)],
        {1: .10, 2: .05, 3: .02, 4: -.02, 5: -.05},
    )
    rows = tuple(
        replace(row, status="HORIZON_UNAVAILABLE", forward_return=None)
        if row.security_id == 2
        else row
        for row in panel.rows
    )
    result = ResearchFactorReturnMethodologyService().compute_factor_return_series(
        replace(panel, rows=rows)
    )
    buckets = result.slices[0].buckets
    assert [bucket.observation_count for bucket in buckets] == [1, 1, 1, 1, 1]
    assert buckets[1].eligible_return_count == 0
    assert result.slices[0].long_short_return == pytest.approx(.15)


def test_minimum_long_leg_coverage_is_explicit():
    panel = return_panel(
        [("A", 1, 5), ("B", 2, 4), ("C", 3, 3), ("D", 4, 2), ("E", 5, 1)],
        {1: .10, 2: .05, 3: .02, 4: -.02, 5: -.05},
    )
    rows = tuple(
        replace(row, status="HORIZON_UNAVAILABLE", forward_return=None)
        if row.security_id == 1
        else row
        for row in panel.rows
    )
    result = ResearchFactorReturnMethodologyService().compute_factor_return_series(
        replace(panel, rows=rows), minimum_observations_per_leg=1
    )
    assert result.slices[0].status == "INSUFFICIENT_LONG_RETURN_OBSERVATIONS"
    assert result.slices[0].long_short_return is None


def test_minimum_short_leg_coverage_is_explicit():
    panel = return_panel(
        [("A", 1, 5), ("B", 2, 4), ("C", 3, 3), ("D", 4, 2), ("E", 5, 1)],
        {1: .10, 2: .05, 3: .02, 4: -.02, 5: -.05},
    )
    rows = tuple(
        replace(row, status="HORIZON_UNAVAILABLE", forward_return=None)
        if row.security_id == 5
        else row
        for row in panel.rows
    )
    result = ResearchFactorReturnMethodologyService().compute_factor_return_series(
        replace(panel, rows=rows), minimum_observations_per_leg=1
    )
    assert result.slices[0].status == "INSUFFICIENT_SHORT_RETURN_OBSERVATIONS"
    assert result.slices[0].long_short_return is None


def test_no_eligible_returns_has_explicit_status():
    panel = return_panel(
        [("A", 1, 5), ("B", 2, 4), ("C", 3, 3), ("D", 4, 2), ("E", 5, 1)],
        {1: .10, 2: .05, 3: .02, 4: -.02, 5: -.05},
    )
    rows = tuple(replace(row, status="HORIZON_UNAVAILABLE", forward_return=None) for row in panel.rows)
    result = ResearchFactorReturnMethodologyService().compute_factor_return_series(
        replace(panel, rows=rows)
    )
    section = result.slices[0]
    assert section.status == "NO_ELIGIBLE_RETURNS"
    assert section.eligible_observation_count == 0
    assert section.long_short_return is None


def test_compute_factor_return_series_distributes_remainder_deterministically():
    panel = return_panel(
        [("A", 1, 7), ("B", 2, 6), ("C", 3, 5), ("D", 4, 4), ("E", 5, 3), ("F", 6, 2), ("G", 7, 1)],
        {i: .01 * i for i in range(1, 8)},
    )
    result = ResearchFactorReturnMethodologyService().compute_factor_return_series(
        panel, bucket_count=5
    )
    assert [bucket.observation_count for bucket in result.slices[0].buckets] == [2, 2, 1, 1, 1]


def test_compute_factor_return_series_is_deterministic_for_input_order():
    panel = return_panel(
        [("A", 1, 5), ("B", 2, 4), ("C", 3, 3), ("D", 4, 2), ("E", 5, 1)],
        {1: .10, 2: .06, 3: .02, 4: -.01, 5: -.05},
    )
    service = ResearchFactorReturnMethodologyService()
    first = service.compute_factor_return_series(panel)
    second = service.compute_factor_return_series(replace(panel, rows=tuple(reversed(panel.rows))))
    assert first == second


@pytest.mark.parametrize("bucket_count", [0, 1, True])
def test_rejects_invalid_bucket_count(bucket_count):
    panel = return_panel([("A", 1, 2), ("B", 2, 1)], {1: .1, 2: -.1})
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnMethodologyService().compute_factor_return_series(
            panel, bucket_count=bucket_count
        )


@pytest.mark.parametrize("minimum", [0, -1, True])
def test_rejects_invalid_minimum_leg_coverage(minimum):
    panel = return_panel([("A", 1, 2), ("B", 2, 1)], {1: .1, 2: -.1})
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnMethodologyService().compute_factor_return_series(
            panel, minimum_observations_per_leg=minimum
        )


def test_rejects_empty_panel():
    panel = ResearchFactorReturnPanel(
        "quality_score", "1", 1, PriceBasis.UNADJUSTED, "policy", ()
    )
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnMethodologyService().compute_factor_return_series(panel)


def test_rejects_factor_identity_mismatch():
    panel = return_panel(
        [("A", 1, 2), ("B", 2, 1)],
        {1: .1, 2: -.1},
    )
    bad_factor = replace(
        panel.rows[0].factor_value,
        factor_key="other_factor",
    )
    bad_row = replace(panel.rows[0], factor_value=bad_factor)
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnMethodologyService().compute_factor_return_series(
            replace(panel, rows=(bad_row, panel.rows[1]))
        )


def test_rejects_symbol_mismatch():
    panel = return_panel(
        [("A", 1, 2), ("B", 2, 1)],
        {1: .1, 2: -.1},
    )
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnMethodologyService().compute_factor_return_series(
            replace(panel, rows=(replace(panel.rows[0], symbol="MSFT"), panel.rows[1]))
        )
