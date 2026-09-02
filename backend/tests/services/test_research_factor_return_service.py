from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from quantcore.core.enums import PriceBasis
from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_cross_sectional_service import (
    ResearchFactorCrossSectionalService,
    ResearchFactorPanel,
    ResearchFactorPanelRow,
)
from quantcore.services.research_factor_return_service import (
    ResearchFactorReturnPanel,
    ResearchFactorReturnService,
)


BASE = datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc)


@dataclass
class Price:
    date: datetime
    close: float
    adjusted_close: float | None


def factor_row(symbol, security_id, as_of, value):
    factor = ResearchFactorValue(
        factor_key="quality_score",
        definition_version="1",
        symbol=symbol,
        security_id=security_id,
        as_of=as_of,
        value_numeric=value,
        unit="score",
    )
    return ResearchFactorPanelRow(symbol, security_id, as_of, factor)


def ranked_panel(*rows):
    panel = ResearchFactorPanel("quality_score", "1", tuple(rows), "score")
    return ResearchFactorCrossSectionalService().rank_factor_panel(panel)


def prices(start, closes, adjusted=True):
    return tuple(
        Price(
            start + timedelta(days=i),
            close,
            close * 1.1 if adjusted else None,
        )
        for i, close in enumerate(closes)
    )


def test_compute_forward_returns_uses_next_price_after_factor_as_of():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    history = {10: prices(datetime(2026, 8, 19, tzinfo=timezone.utc), [100, 110, 121, 133.1])}

    result = ResearchFactorReturnService().compute_forward_returns(
        panel, history, horizon=1, return_price_basis=PriceBasis.UNADJUSTED
    )

    assert isinstance(result, ResearchFactorReturnPanel)
    row = result.rows[0]
    assert row.entry_date == datetime(2026, 8, 20, tzinfo=timezone.utc)
    assert row.exit_date == datetime(2026, 8, 21, tzinfo=timezone.utc)
    assert row.entry_price == 110.0
    assert row.exit_price == 121.0
    assert row.forward_return == pytest.approx(0.1)
    assert row.status == "AVAILABLE"


def test_compute_forward_returns_uses_adjusted_close_when_requested():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    history = {10: prices(datetime(2026, 8, 19, tzinfo=timezone.utc), [100, 110, 121])}

    result = ResearchFactorReturnService().compute_forward_returns(
        panel, history, horizon=1
    )

    row = result.rows[0]
    assert row.entry_price == pytest.approx(121.0)
    assert row.exit_price == pytest.approx(133.1)
    assert row.forward_return == pytest.approx(0.1)
    assert row.return_price_basis is PriceBasis.ADJUSTED


def test_compute_forward_returns_preserves_horizon_unavailable_rows():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    history = {10: prices(datetime(2026, 8, 19, tzinfo=timezone.utc), [100, 110])}

    result = ResearchFactorReturnService().compute_forward_returns(
        panel, history, horizon=2, return_price_basis=PriceBasis.UNADJUSTED
    )

    row = result.rows[0]
    assert row.status == "HORIZON_UNAVAILABLE"
    assert row.forward_return is None


def test_compute_forward_returns_aligns_each_security_independently():
    as_of = BASE
    panel = ranked_panel(
        factor_row("AAPL", 10, as_of, 0.8),
        factor_row("MSFT", 20, as_of, 0.2),
    )
    history = {
        10: prices(datetime(2026, 8, 19, tzinfo=timezone.utc), [100, 110, 121]),
        20: prices(datetime(2026, 8, 19, tzinfo=timezone.utc), [200, 180, 171]),
    }

    result = ResearchFactorReturnService().compute_forward_returns(
        panel, history, horizon=1, return_price_basis=PriceBasis.UNADJUSTED
    )

    returns = {row.symbol: row.forward_return for row in result.rows}
    assert returns["AAPL"] == pytest.approx(0.1)
    assert returns["MSFT"] == pytest.approx(-0.05)


def test_compute_forward_returns_accepts_unsorted_price_history():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    history = {10: (Price(start + timedelta(days=2), 121, 121), Price(start, 100, 100), Price(start + timedelta(days=1), 110, 110))}

    result = ResearchFactorReturnService().compute_forward_returns(
        panel, history, horizon=1, return_price_basis=PriceBasis.UNADJUSTED
    )

    assert result.rows[0].forward_return == pytest.approx(0.1)


def test_compute_forward_returns_rejects_non_positive_horizon():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(
            panel, {}, horizon=0
        )


def test_compute_forward_returns_rejects_boolean_horizon():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(
            panel, {}, horizon=True
        )


def test_compute_forward_returns_rejects_missing_adjusted_close():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    history = (Price(start, 100, 100), Price(start + timedelta(days=1), 110, None), Price(start + timedelta(days=2), 121, 121))
    history = {10: history}

    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(panel, history, horizon=1)


def test_compute_forward_returns_rejects_duplicate_price_dates():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    history = {10: (Price(start, 100, 100), Price(start, 101, 101))}

    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(
            panel, history, horizon=1
        )


def test_compute_forward_returns_rejects_non_finite_price():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    history = {10: (Price(start, float("nan"), 100), Price(start + timedelta(days=1), 110, 110))}

    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(
            panel, history, horizon=1, return_price_basis=PriceBasis.UNADJUSTED
        )


def test_compute_forward_returns_rejects_non_positive_selected_price():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    start = datetime(2026, 8, 19, tzinfo=timezone.utc)
    history = {10: (Price(start, 100, 100), Price(start + timedelta(days=1), 0, 0), Price(start + timedelta(days=2), 110, 110))}

    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(
            panel, history, horizon=1, return_price_basis=PriceBasis.UNADJUSTED
        )


def test_compute_forward_returns_does_not_use_price_at_factor_timestamp():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    history = {
        10: (
            Price(BASE, 999, 999),
            Price(BASE + timedelta(days=1), 100, 100),
            Price(BASE + timedelta(days=2), 105, 105),
        )
    }

    result = ResearchFactorReturnService().compute_forward_returns(
        panel, history, horizon=1, return_price_basis=PriceBasis.UNADJUSTED
    )

    assert result.rows[0].entry_price == 100
    assert result.rows[0].forward_return == pytest.approx(0.05)


def test_compute_forward_returns_rejects_invalid_price_basis():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(
            panel, {}, horizon=1, return_price_basis="ADJUSTED"
        )


def test_compute_forward_returns_preserves_factor_provenance():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    history = {10: prices(datetime(2026, 8, 19, tzinfo=timezone.utc), [100, 110, 121])}

    result = ResearchFactorReturnService().compute_forward_returns(
        panel, history, horizon=1, return_price_basis=PriceBasis.UNADJUSTED
    )

    row = result.rows[0]
    assert row.factor_value.factor_key == "quality_score"
    assert row.factor_value.definition_version == "1"
    assert row.factor_rank == 1.0
    assert row.normalized_rank == 0.5


def test_compute_forward_returns_rejects_future_factor_as_of():
    future = datetime.now(timezone.utc) + timedelta(days=1)
    panel = ranked_panel(factor_row("AAPL", 10, future, 0.5))
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(
            panel, {}, horizon=1
        )


def test_compute_forward_returns_requires_timezone_aware_price_dates():
    panel = ranked_panel(factor_row("AAPL", 10, BASE, 0.5))
    history = {10: (Price(datetime(2026, 8, 20), 100, 100),)}
    with pytest.raises(InvalidInputError):
        ResearchFactorReturnService().compute_forward_returns(
            panel, history, horizon=1
        )
