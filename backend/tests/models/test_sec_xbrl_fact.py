from datetime import date
from decimal import Decimal

from quantcore.models.sec_xbrl_fact import SECXBRLFactObservation


def test_sec_xbrl_fact_observation_preserves_revision_identity():
    observation = SECXBRLFactObservation(
        company_id=1,
        accession_number="0000320193-24-000123",
        taxonomy="us-gaap",
        concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        unit="USD",
        value=Decimal("391035000000"),
        period_start=date(2023, 10, 1),
        period_end=date(2024, 9, 28),
        filed_at=date(2024, 11, 1),
        form="10-K",
        fiscal_year=2024,
        fiscal_period="FY",
    )

    assert observation.accession_number == "0000320193-24-000123"
    assert observation.taxonomy == "us-gaap"
    assert observation.concept.startswith("Revenue")
    assert observation.value == Decimal("391035000000")


def test_sec_xbrl_fact_observation_has_revision_and_filing_columns():
    columns = SECXBRLFactObservation.__table__.c
    assert columns.identity_hash.unique is True
    assert columns.accession_number.unique is not True
    assert columns.filing_id.foreign_keys
    assert columns.filed_at.index is True
    assert columns.accepted_at.index is True
    assert any(
        constraint.name == "uq_sec_xbrl_fact_observation_identity"
        for constraint in SECXBRLFactObservation.__table__.constraints
    )
