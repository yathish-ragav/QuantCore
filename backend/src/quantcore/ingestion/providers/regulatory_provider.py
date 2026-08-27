from abc import ABC, abstractmethod

from quantcore.schemas.sec_filing import SECFilingData
from quantcore.schemas.sec_xbrl_fact import SECXBRLFactObservationData


class RegulatoryDataProvider(ABC):
    """Provider interface for regulatory filing metadata."""

    @abstractmethod
    def get_sec_filings(
        self,
        cik: str,
    ) -> list[SECFilingData]:
        pass

    @abstractmethod
    def get_sec_xbrl_fact_observations(
        self,
        cik: str,
    ) -> list[SECXBRLFactObservationData]:
        pass
