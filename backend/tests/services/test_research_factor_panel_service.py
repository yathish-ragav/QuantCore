from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.services.research_dataset_service import ResearchFeatureVector
from quantcore.services.research_factor_computation_service import ResearchFactorValue
from quantcore.services.research_factor_panel_service import (
    ResearchFactorPanel,
    ResearchFactorPanelRow,
    ResearchFactorPanelService,
)
from quantcore.services.research_historical_analysis_service import (
    ResearchHistoricalDataset,
    ResearchHistoricalDatasetRow,
)


AS_OF_1 = datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc)
AS_OF_2 = datetime(2026, 8, 20, 15, 30, tzinfo=timezone.utc)


def make_row(symbol, security_id, as_of, value):
    vector = ResearchFeatureVector(
        symbol=symbol,
        security_id=security_id,
        as_of=as_of,
        features=(),
    )
    return ResearchHistoricalDatasetRow(
        symbol=symbol,
        security_id=security_id,
        as_of=as_of,
        feature_vector=vector,
    )


def make_service():
    computation = Mock()
    computation.compute_factor.side_effect = lambda vector, *, factor_key, definition_version: ResearchFactorValue(
        factor_key=factor_key,
        definition_version=definition_version,
        symbol=vector.symbol.strip().upper(),
        security_id=vector.security_id,
        as_of=vector.as_of,
        value_numeric=vector.security_id / 10,
        unit="score",
        input_manifest={"source": "test"},
    )
    service = ResearchFactorPanelService.__new__(ResearchFactorPanelService)
    service.computation_service = computation
    return service


def dataset(*rows):
    return ResearchHistoricalDataset(rows=tuple(rows), definition_identities=None)


def test_build_factor_panel_computes_one_factor_for_every_historical_row_in_order():
    service = make_service()
    result = service.build_factor_panel(
        dataset(
            make_row("MSFT", 20, AS_OF_2, 2),
            make_row("AAPL", 10, AS_OF_1, 1),
            make_row("AAPL", 10, AS_OF_2, 1),
        ),
        factor_key=" quality_score ",
        definition_version=" 1 ",
    )

    assert isinstance(result, ResearchFactorPanel)
    assert (result.factor_key, result.definition_version, result.unit) == (
        "quality_score",
        "1",
        "score",
    )
    assert [(row.symbol, row.as_of) for row in result.rows] == [
        ("AAPL", AS_OF_1),
        ("AAPL", AS_OF_2),
        ("MSFT", AS_OF_2),
    ]
    assert all(isinstance(row, ResearchFactorPanelRow) for row in result.rows)
    assert service.computation_service.compute_factor.call_count == 3


def test_build_factor_panel_preserves_factor_provenance_and_identity():
    service = make_service()
    result = service.build_factor_panel(
        dataset(make_row("AAPL", 10, AS_OF_1, 1)),
        factor_key="quality_score",
        definition_version="1",
    )

    value = result.rows[0].factor_value
    assert (value.factor_key, value.definition_version) == ("quality_score", "1")
    assert value.input_manifest == {"source": "test"}


def test_build_factor_panel_rejects_empty_dataset():
    service = make_service()
    with pytest.raises(InvalidInputError):
        service.build_factor_panel(
            dataset(), factor_key="quality_score", definition_version="1"
        )


def test_build_factor_panel_rejects_duplicate_security_as_of_rows():
    service = make_service()
    with pytest.raises(InvalidInputError):
        service.build_factor_panel(
            dataset(
                make_row("AAPL", 10, AS_OF_1, 1),
                make_row("AAPL", 10, AS_OF_1, 1),
            ),
            factor_key="quality_score",
            definition_version="1",
        )


def test_build_factor_panel_rejects_row_feature_vector_identity_mismatch():
    service = make_service()
    row = make_row("AAPL", 10, AS_OF_1, 1)
    row = ResearchHistoricalDatasetRow(
        symbol="MSFT",
        security_id=row.security_id,
        as_of=row.as_of,
        feature_vector=row.feature_vector,
    )
    with pytest.raises(InvalidInputError):
        service.build_factor_panel(
            dataset(row), factor_key="quality_score", definition_version="1"
        )


def test_build_factor_panel_rejects_future_historical_boundary():
    service = make_service()
    future = datetime.now(timezone.utc).replace(microsecond=0).replace(year=2030)
    with pytest.raises(InvalidInputError):
        service.build_factor_panel(
            dataset(make_row("AAPL", 10, future, 1)),
            factor_key="quality_score",
            definition_version="1",
        )
