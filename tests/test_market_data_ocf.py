from __future__ import annotations

import pandas as pd

from src.market_data import _extract_ocf_data


class _DummyTicker:
    def __init__(self, quarterly_cashflow: pd.DataFrame, cashflow: pd.DataFrame):
        self.quarterly_cashflow = quarterly_cashflow
        self.cashflow = cashflow


def test_ocf_prefers_statement_over_info_value() -> None:
    qcf = pd.DataFrame()
    cf = pd.DataFrame(
        {
            pd.Timestamp("2024-12-31"): [123.0],
        },
        index=["Operating Cash Flow"],
    )
    ticker = _DummyTicker(quarterly_cashflow=qcf, cashflow=cf)

    ocf_q, ocf_ttm, ocf_y = _extract_ocf_data(ticker, {"operatingCashflow": -999.0})

    assert ocf_q == []
    assert ocf_ttm == 123.0
    assert ocf_y == [123.0]


def test_ocf_row_pattern_fallback_works() -> None:
    qcf = pd.DataFrame(
        {
            pd.Timestamp("2024-12-31"): [10.0],
            pd.Timestamp("2024-09-30"): [20.0],
        },
        index=["Cash Flow from Continuing Operating Activities"],
    )
    cf = pd.DataFrame()
    ticker = _DummyTicker(quarterly_cashflow=qcf, cashflow=cf)

    ocf_q, ocf_ttm, ocf_y = _extract_ocf_data(ticker, {})

    assert ocf_q == [10.0, 20.0]
    assert ocf_ttm == 60.0
    assert ocf_y == []
