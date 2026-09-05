from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.ingestion_orchestrator import IngestionResult


class IngestionQualityStatus(str, Enum):
    """Deterministic completeness state for one ingestion execution."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NO_TARGETS = "NO_TARGETS"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True)
class IngestionQualityAssessment:
    """Coverage/completeness assessment of an ingestion execution."""

    dataset: object
    status: IngestionQualityStatus
    eligible: int
    attempted: int
    succeeded: int
    skipped: int
    failed: int
    coverage_ratio: float

    @property
    def is_complete(self) -> bool:
        return self.status is IngestionQualityStatus.COMPLETE


class IngestionQualityService:
    """Assess ingestion coverage without re-validating persisted observations."""

    @staticmethod
    def assess(result: IngestionResult) -> IngestionQualityAssessment:
        if result.eligible < 0:
            raise InvalidInputError("Ingestion eligible count must not be negative.")

        counts = (
            result.attempted,
            result.succeeded,
            result.skipped,
            result.failed,
        )
        if any(count < 0 for count in counts):
            raise InvalidInputError("Ingestion execution counts must not be negative.")

        if result.attempted != result.succeeded + result.failed:
            status = IngestionQualityStatus.INCONSISTENT
        elif result.eligible != result.succeeded + result.skipped + result.failed:
            status = IngestionQualityStatus.INCONSISTENT
        elif result.eligible == 0:
            status = IngestionQualityStatus.NO_TARGETS
        elif result.failed == result.eligible:
            status = IngestionQualityStatus.FAILED
        elif result.failed > 0:
            status = IngestionQualityStatus.PARTIAL
        else:
            status = IngestionQualityStatus.COMPLETE

        coverage_ratio = (
            0.0
            if result.eligible == 0
            else (result.succeeded + result.skipped) / result.eligible
        )

        return IngestionQualityAssessment(
            dataset=result.dataset,
            status=status,
            eligible=result.eligible,
            attempted=result.attempted,
            succeeded=result.succeeded,
            skipped=result.skipped,
            failed=result.failed,
            coverage_ratio=coverage_ratio,
        )
