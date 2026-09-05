import pytest

from quantcore.ingestion.datasets import IngestionDataset
from quantcore.services.ingestion_orchestrator import IngestionResult
from quantcore.services.ingestion_quality_service import (
    IngestionQualityService,
    IngestionQualityStatus,
)


def result(eligible, attempted, succeeded, skipped, failed):
    return IngestionResult(
        dataset=IngestionDataset.PRICE_HISTORY,
        eligible=eligible,
        attempted=attempted,
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
        errors=(),
    )


def test_complete_when_all_targets_succeed_or_are_skipped():
    assessment = IngestionQualityService.assess(
        result(eligible=3, attempted=2, succeeded=2, skipped=1, failed=0)
    )

    assert assessment.status is IngestionQualityStatus.COMPLETE
    assert assessment.coverage_ratio == pytest.approx(1.0)
    assert assessment.is_complete


def test_partial_when_some_targets_fail():
    assessment = IngestionQualityService.assess(
        result(eligible=4, attempted=3, succeeded=2, skipped=1, failed=1)
    )

    assert assessment.status is IngestionQualityStatus.PARTIAL
    assert assessment.coverage_ratio == pytest.approx(0.75)


def test_failed_when_every_target_fails():
    assessment = IngestionQualityService.assess(
        result(eligible=2, attempted=2, succeeded=0, skipped=0, failed=2)
    )

    assert assessment.status is IngestionQualityStatus.FAILED
    assert assessment.coverage_ratio == pytest.approx(0.0)


def test_no_targets_is_explicit():
    assessment = IngestionQualityService.assess(
        result(eligible=0, attempted=0, succeeded=0, skipped=0, failed=0)
    )

    assert assessment.status is IngestionQualityStatus.NO_TARGETS
    assert assessment.coverage_ratio == pytest.approx(0.0)


def test_inconsistent_counts_are_rejected_as_quality_state():
    assessment = IngestionQualityService.assess(
        result(eligible=3, attempted=2, succeeded=2, skipped=0, failed=0)
    )

    assert assessment.status is IngestionQualityStatus.INCONSISTENT


@pytest.mark.parametrize(
    "values",
    [
        (-1, 0, 0, 0, 0),
        (1, -1, 0, 1, 0),
        (1, 1, -1, 2, 0),
        (1, 1, 1, 0, -1),
    ],
)
def test_negative_counts_are_rejected(values):
    with pytest.raises(Exception):
        IngestionQualityService.assess(result(*values))
