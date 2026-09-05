from quantcore.core.exceptions import DataValidationError, ExternalDataError
from quantcore.ingestion.retry import (
    IngestionFailureClass,
    IngestionRetryPolicy,
    classify_ingestion_failure,
)


def test_external_failure_is_transient():
    assert (
        classify_ingestion_failure(ExternalDataError("provider unavailable"))
        is IngestionFailureClass.TRANSIENT
    )


def test_validation_failure_is_permanent():
    assert (
        classify_ingestion_failure(DataValidationError("bad payload"))
        is IngestionFailureClass.PERMANENT
    )


def test_retry_policy_is_bounded_and_deterministic():
    policy = IngestionRetryPolicy(
        max_attempts=3,
        base_delay_seconds=0.5,
        max_delay_seconds=2.0,
    )

    assert policy.should_retry(ExternalDataError("timeout"), 1) is True
    assert policy.should_retry(ExternalDataError("timeout"), 2) is True
    assert policy.should_retry(ExternalDataError("timeout"), 3) is False
    assert policy.should_retry(DataValidationError("bad"), 1) is False

    assert policy.delay_seconds(1) == 0.5
    assert policy.delay_seconds(2) == 1.0
    assert policy.delay_seconds(3) == 2.0


def test_retry_policy_rejects_invalid_configuration():
    for kwargs in (
        {"max_attempts": 0},
        {"base_delay_seconds": -1},
        {"max_delay_seconds": -1},
        {"base_delay_seconds": 2, "max_delay_seconds": 1},
    ):
        try:
            IngestionRetryPolicy(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")
