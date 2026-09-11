from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_dataset_service import ResearchFeatureVector
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalAnalysisService,
    ResearchHistoricalDataset,
    ResearchHistoricalDatasetRow,
)


def make_vector(symbol, security_id, as_of):
    return ResearchFeatureVector(
        symbol=symbol,
        security_id=security_id,
        as_of=as_of,
        features=(),
    )


def make_service():
    service = ResearchHistoricalAnalysisService.__new__(
        ResearchHistoricalAnalysisService
    )
    service.db = Mock()
    service.dataset_service = Mock()
    return service


def test_build_historical_dataset_builds_deterministic_chronological_panel():
    service = make_service()
    first = datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc)
    second = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)

    def build(symbol, *, as_of, definition_identities=None):
        return make_vector(symbol, 10 if symbol == "AAPL" else 20, as_of)

    service.dataset_service.build_feature_vector.side_effect = build

    result = service.build_historical_dataset(
        [" msft ", "aapl"],
        as_ofs=[second, first],
    )

    assert isinstance(result, ResearchHistoricalDataset)
    assert [(row.symbol, row.as_of) for row in result.rows] == [
        ("AAPL", first),
        ("MSFT", first),
        ("AAPL", second),
        ("MSFT", second),
    ]
    assert all(isinstance(row, ResearchHistoricalDatasetRow) for row in result.rows)
    assert [row.security_id for row in result.rows] == [10, 20, 10, 20]
    assert service.dataset_service.build_feature_vector.call_count == 4


def test_build_historical_dataset_normalizes_naive_timestamps_and_symbols():
    service = make_service()
    as_of = datetime(2026, 8, 20, 15, 30)
    service.dataset_service.build_feature_vector.return_value = make_vector(
        "AAPL", 10, as_of.replace(tzinfo=timezone.utc)
    )

    result = service.build_historical_dataset(
        [" aapl "],
        as_ofs=[as_of],
    )

    assert result.rows[0].symbol == "AAPL"
    assert result.rows[0].as_of == as_of.replace(tzinfo=timezone.utc)
    service.dataset_service.build_feature_vector.assert_called_once_with(
        "AAPL",
        as_of=as_of.replace(tzinfo=timezone.utc),
        definition_identities=None,
    )


def test_build_historical_dataset_preserves_explicit_definition_schema():
    service = make_service()
    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)
    service.dataset_service.build_feature_vector.return_value = make_vector(
        "AAPL", 10, as_of
    )

    result = service.build_historical_dataset(
        ["AAPL"],
        as_ofs=[as_of],
        definition_identities=[(" operating_margin ", " 1 "), ("net_margin", "2")],
    )

    assert result.definition_identities == (
        ("operating_margin", "1"),
        ("net_margin", "2"),
    )
    service.dataset_service.build_feature_vector.assert_called_once_with(
        "AAPL",
        as_of=as_of,
        definition_identities=(
            ("operating_margin", "1"),
            ("net_margin", "2"),
        ),
    )


def test_build_historical_dataset_rejects_duplicate_symbols_before_reads():
    service = make_service()

    with pytest.raises(InvalidInputError, match="symbols must not contain duplicates"):
        service.build_historical_dataset(
            ["AAPL", " aapl "],
            as_ofs=[datetime(2026, 8, 20, tzinfo=timezone.utc)],
        )

    service.dataset_service.build_feature_vector.assert_not_called()


def test_build_historical_dataset_rejects_duplicate_as_ofs_before_reads():
    service = make_service()
    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)

    with pytest.raises(InvalidInputError, match="as-of timestamps must not contain duplicates"):
        service.build_historical_dataset(
            ["AAPL"],
            as_ofs=[as_of, as_of],
        )

    service.dataset_service.build_feature_vector.assert_not_called()


def test_build_historical_dataset_rejects_empty_inputs_before_reads():
    service = make_service()
    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)

    with pytest.raises(InvalidInputError, match="At least one research symbol"):
        service.build_historical_dataset([], as_ofs=[as_of])
    with pytest.raises(InvalidInputError, match="At least one historical as-of"):
        service.build_historical_dataset(["AAPL"], as_ofs=[])
    with pytest.raises(InvalidInputError, match="At least one definition identity"):
        service.build_historical_dataset(
            ["AAPL"], as_ofs=[as_of], definition_identities=[]
        )

    service.dataset_service.build_feature_vector.assert_not_called()


def test_build_historical_dataset_rejects_future_timestamp_before_reads():
    service = make_service()
    future = datetime.now(timezone.utc).replace(microsecond=0).replace(
        year=datetime.now(timezone.utc).year + 1
    )

    with pytest.raises(InvalidInputError, match="must not be in the future"):
        service.build_historical_dataset(["AAPL"], as_ofs=[future])

    service.dataset_service.build_feature_vector.assert_not_called()


def test_historical_dataset_fingerprint_is_deterministic_and_binds_rows():
    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)
    first_vector = make_vector("AAPL", 10, as_of)
    second_vector = make_vector("MSFT", 20, as_of)
    first = ResearchHistoricalDataset(
        rows=(
            ResearchHistoricalDatasetRow("AAPL", 10, as_of, first_vector),
            ResearchHistoricalDatasetRow("MSFT", 20, as_of, second_vector),
        ),
        definition_identities=None,
    )
    second = ResearchHistoricalDataset(
        rows=(
            ResearchHistoricalDatasetRow("AAPL", 10, as_of, first_vector),
            ResearchHistoricalDatasetRow("MSFT", 20, as_of, second_vector),
        ),
        definition_identities=None,
    )

    assert len(first.dataset_fingerprint) == 64
    assert first.dataset_fingerprint == second.dataset_fingerprint

    changed_vector = make_vector("MSFT", 21, as_of)
    changed = ResearchHistoricalDataset(
        rows=(
            ResearchHistoricalDatasetRow("AAPL", 10, as_of, first_vector),
            ResearchHistoricalDatasetRow("MSFT", 21, as_of, changed_vector),
        ),
        definition_identities=None,
    )
    assert changed.dataset_fingerprint != first.dataset_fingerprint


def test_historical_dataset_fingerprint_binds_definition_schema():
    as_of = datetime(2026, 8, 20, tzinfo=timezone.utc)
    vector = make_vector("AAPL", 10, as_of)
    first = ResearchHistoricalDataset(
        rows=(ResearchHistoricalDatasetRow("AAPL", 10, as_of, vector),),
        definition_identities=(("net_margin", "1"),),
    )
    second = ResearchHistoricalDataset(
        rows=(ResearchHistoricalDatasetRow("AAPL", 10, as_of, vector),),
        definition_identities=(("net_margin", "2"),),
    )

    assert first.dataset_fingerprint != second.dataset_fingerprint

def test_historical_dataset_fingerprint_is_independent_of_row_and_definition_order():
    first_as_of = datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc)
    second_as_of = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)
    first = ResearchHistoricalDataset(
        rows=(
            ResearchHistoricalDatasetRow(
                symbol="MSFT",
                security_id=20,
                as_of=second_as_of,
                feature_vector=make_vector("MSFT", 20, second_as_of),
            ),
            ResearchHistoricalDatasetRow(
                symbol="AAPL",
                security_id=10,
                as_of=first_as_of,
                feature_vector=make_vector("AAPL", 10, first_as_of),
            ),
        ),
        definition_identities=(("z_metric", "1"), ("a_metric", "1")),
    )
    second = ResearchHistoricalDataset(
        rows=tuple(reversed(first.rows)),
        definition_identities=tuple(reversed(first.definition_identities)),
    )

    assert first.dataset_fingerprint == second.dataset_fingerprint
