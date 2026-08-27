from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class MacroFreshnessPolicy:
    """Scheduling policy for one managed macroeconomic series."""

    max_age: timedelta
    description: str


# This is the deliberately small initial managed macro universe. It is a
# scheduler registry, not a claim that these are all economically relevant
# series available from FRED.
MACRO_SERIES_POLICIES: dict[str, MacroFreshnessPolicy] = {
    "GDP": MacroFreshnessPolicy(
        max_age=timedelta(days=2),
        description="GDP is checked frequently enough to capture scheduled releases and revisions.",
    ),
    "CPIAUCSL": MacroFreshnessPolicy(
        max_age=timedelta(days=2),
        description="CPI is checked around scheduled releases and revisions.",
    ),
    "UNRATE": MacroFreshnessPolicy(
        max_age=timedelta(days=2),
        description="Unemployment data is checked around scheduled releases and revisions.",
    ),
    "FEDFUNDS": MacroFreshnessPolicy(
        max_age=timedelta(days=2),
        description="The effective federal funds rate is refreshed frequently.",
    ),
    "DGS10": MacroFreshnessPolicy(
        max_age=timedelta(days=1),
        description="The 10-year Treasury constant maturity rate is checked daily.",
    ),
}


def normalize_series_ids(series_ids: list[str] | None = None) -> list[str]:
    """Return normalized, deduplicated managed/explicit series identifiers."""
    if series_ids is None:
        return list(MACRO_SERIES_POLICIES)

    return list(
        dict.fromkeys(
            series_id.strip().upper()
            for series_id in series_ids
            if series_id and series_id.strip()
        )
    )
