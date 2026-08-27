from unittest.mock import Mock, patch

import pandas as pd

from quantcore.core.enums import CorporateActionType
from quantcore.ingestion.providers.yahoo import YahooClient
from quantcore.schemas.corporate_action import CorporateActionData


def test_yahoo_get_corporate_actions():
    fake_ticker = Mock()
    dates = pd.to_datetime(["2024-01-02", "2024-08-12", "2024-11-01"])

    fake_ticker.history.return_value = pd.DataFrame(
        {
            "Dividends": [0.0, 0.25, 0.0],
            "Stock Splits": [0.0, 0.0, 4.0],
        },
        index=dates,
    )

    with patch(
        "quantcore.ingestion.providers.yahoo.yf.Ticker",
        return_value=fake_ticker,
    ):
        result = YahooClient().get_corporate_actions(
            "AAPL",
            period="max",
        )

    fake_ticker.history.assert_called_once_with(
        period="max",
        auto_adjust=False,
        actions=True,
    )

    assert len(result) == 2
    assert all(isinstance(item, CorporateActionData) for item in result)

    assert result[0].effective_date == dates[1].date()
    assert result[0].action_type is CorporateActionType.DIVIDEND
    assert result[0].amount == 0.25

    assert result[1].effective_date == dates[2].date()
    assert result[1].action_type is CorporateActionType.STOCK_SPLIT
    assert result[1].split_ratio == 4.0
