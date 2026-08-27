from abc import ABC, abstractmethod
from datetime import date

from quantcore.schemas.macro import MacroObservationData, MacroSeriesData


class MacroDataProvider(ABC):
    """Provider boundary for economic series and point-in-time observations."""

    SOURCE: str

    @abstractmethod
    def get_series(self, series_id: str) -> MacroSeriesData:
        pass

    @abstractmethod
    def get_observations(
        self,
        series_id: str,
        *,
        vintage_date: date | None = None,
    ) -> list[MacroObservationData]:
        pass
