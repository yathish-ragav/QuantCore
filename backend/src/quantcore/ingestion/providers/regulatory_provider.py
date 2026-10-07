from abc import ABC, abstractmethod
from typing import ClassVar

from quantcore.schemas.sec_filing import SECFilingData
from quantcore.schemas.sec_xbrl_fact import SECXBRLFactObservationData


class RegulatoryDataProvider(ABC):
    SOURCE: ClassVar[str]
    """Provider interface for regulatory filing metadata."""

    @abstractmethod
    def get_sec_filings(
        self,
        cik: str,
    ) -> list[SECFilingData]: ...

    @abstractmethod
    def get_sec_xbrl_fact_observations(
        self,
        cik: str,
    ) -> list[SECXBRLFactObservationData]: ...
