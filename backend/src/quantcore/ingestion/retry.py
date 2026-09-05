"""Deterministic retry policy for ingestion execution.

The policy is intentionally small and synchronous. It classifies only transport/
upstream failures as retryable and leaves validation, configuration, and input
errors as terminal failures.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Type

from quantcore.core.exceptions import ExternalDataError


class IngestionFailureClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"


_RETRYABLE_EXCEPTIONS: tuple[Type[BaseException], ...] = (
    ExternalDataError,
    TimeoutError,
    ConnectionError,
)


def classify_ingestion_failure(exc: BaseException) -> IngestionFailureClass:
    """Classify an ingestion exception without inspecting provider internals."""
    if isinstance(exc, _RETRYABLE_EXCEPTIONS):
        return IngestionFailureClass.TRANSIENT
    return IngestionFailureClass.PERMANENT


@dataclass(frozen=True)
class IngestionRetryPolicy:
    """Bounded deterministic retry policy for one security/dataset operation."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one.")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must not be negative.")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds must not be negative.")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                "max_delay_seconds must be greater than or equal to base_delay_seconds."
            )

    def should_retry(self, exc: BaseException, attempt: int) -> bool:
        """Return whether a failed attempt may be retried."""
        if attempt < 1 or attempt >= self.max_attempts:
            return False
        return classify_ingestion_failure(exc) is IngestionFailureClass.TRANSIENT

    def delay_seconds(self, attempt: int) -> float:
        """Return deterministic exponential backoff after the given attempt."""
        if attempt < 1:
            raise ValueError("attempt must be at least one.")
        delay = self.base_delay_seconds * (2 ** (attempt - 1))
        return min(delay, self.max_delay_seconds)
