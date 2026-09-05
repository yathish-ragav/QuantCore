from datetime import datetime, timezone, timedelta

import pytest

from quantcore.services.historical_coverage_service import (
    HistoricalCoverageService,
    HistoricalCoverageStatus,
)

UTC = timezone.utc
BASE = datetime(2026, 1, 2, 15, 30, tzinfo=UTC)


def dates(count):
    return tuple(BASE + timedelta(days=index) for index in range(count))


def test_complete_coverage_is_deterministic():
    expected = dates(4)
    observed = dates(4)

    first = HistoricalCoverageService().assess(
        start_at=expected[0],
        end_at=expected[-1],
        expected_dates=expected,
        observed_dates=observed,
    )
    second = HistoricalCoverageService().assess(
        start_at=expected[0],
        end_at=expected[-1],
        expected_dates=tuple(reversed(expected)),
        observed_dates=tuple(reversed(observed)),
    )

    assert first == second
    assert first.status is HistoricalCoverageStatus.COMPLETE
    assert first.coverage_ratio == pytest.approx(1.0)
    assert first.missing_dates == ()
    assert first.gap_count == 0
    assert first.max_gap_observations == 0


def test_partial_coverage_reports_missing_observations_and_continuity():
    expected = dates(7)
    observed = (expected[0], expected[1], expected[4], expected[6])

    result = HistoricalCoverageService().assess(
        start_at=expected[0],
        end_at=expected[-1],
        expected_dates=expected,
        observed_dates=observed,
    )

    assert result.status is HistoricalCoverageStatus.PARTIAL
    assert result.expected_count == 7
    assert result.observed_count == 4
    assert result.missing_count == 3
    assert result.coverage_ratio == pytest.approx(4 / 7)
    assert result.missing_dates == (expected[2], expected[3], expected[5])
    assert result.gap_count == 2
    assert result.max_gap_observations == 2
    assert result.first_observed_at == expected[0]
    assert result.last_observed_at == expected[6]


def test_no_observations_is_explicit():
    expected = dates(3)

    result = HistoricalCoverageService().assess(
        start_at=expected[0],
        end_at=expected[-1],
        expected_dates=expected,
        observed_dates=(),
    )

    assert result.status is HistoricalCoverageStatus.NO_OBSERVATIONS
    assert result.coverage_ratio == pytest.approx(0.0)
    assert result.has_gaps


def test_empty_expected_schedule_is_not_called_complete():
    result = HistoricalCoverageService().assess(
        start_at=BASE,
        end_at=BASE,
        expected_dates=(),
        observed_dates=(),
    )

    assert result.status is HistoricalCoverageStatus.NO_EXPECTED_OBSERVATIONS
    assert not result.is_complete
    assert result.coverage_ratio == pytest.approx(0.0)


@pytest.mark.parametrize(
    "expected, observed",
    [
        (dates(3) + (dates(3)[-1],), dates(3)),
        (dates(3), dates(3) + (dates(3)[-1],)),
    ],
)
def test_duplicate_timestamps_are_rejected(expected, observed):
    with pytest.raises(ValueError):
        HistoricalCoverageService().assess(
            start_at=BASE,
            end_at=BASE + timedelta(days=2),
            expected_dates=expected,
            observed_dates=observed,
        )


def test_out_of_range_observation_is_rejected():
    expected = dates(2)

    with pytest.raises(ValueError):
        HistoricalCoverageService().assess(
            start_at=expected[0],
            end_at=expected[-1],
            expected_dates=expected,
            observed_dates=(expected[0] - timedelta(days=1),),
        )


def test_naive_datetime_is_rejected():
    expected = dates(2)

    with pytest.raises(ValueError):
        HistoricalCoverageService().assess(
            start_at=expected[0].replace(tzinfo=None),
            end_at=expected[-1],
            expected_dates=expected,
            observed_dates=expected,
        )


def test_weekends_or_holidays_are_not_assumed_to_be_missing():
    expected = (BASE, BASE + timedelta(days=3))
    observed = expected

    result = HistoricalCoverageService().assess(
        start_at=BASE,
        end_at=expected[-1],
        expected_dates=expected,
        observed_dates=observed,
    )

    assert result.is_complete
    assert result.missing_count == 0


def test_observation_not_in_expected_schedule_is_rejected():
    expected = dates(2)

    with pytest.raises(ValueError):
        HistoricalCoverageService().assess(
            start_at=expected[0],
            end_at=expected[-1],
            expected_dates=expected,
            observed_dates=(expected[0] + timedelta(days=2),),
        )
