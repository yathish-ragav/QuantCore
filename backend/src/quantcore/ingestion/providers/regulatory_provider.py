from abc import ABC, abstractmethod

from quantcore.schemas.sec_filing import SECFilingData


class RegulatoryDataProvider(ABC):
    """Provider interface for regulatory filing metadata."""

    @abstractmethod
    def get_sec_filings(
        self,
        cik: str,
    ) -> list[SECFilingData]:
        pass
