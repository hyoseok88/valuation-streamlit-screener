import numpy as np

from src.metrics import classify_sales_trend, compute_multiple, evaluate_vip
from src.models import FundamentalSnapshot


def _snapshot(market_cap, ocf_q, revenue_y, prices, ocf_ttm=None):
    from datetime import datetime, timezone

    return FundamentalSnapshot(
        market_cap=market_cap,
        ocf_q=ocf_q,
        ocf_ttm=ocf_ttm,
        revenue_y=revenue_y,
        asof_date=datetime.now(timezone.utc),
        sector="Tech",
        currency="USD",
        price_series=prices,
    )


def test_compute_multiple_ok():
    snap = _snapshot(1000.0, [20.0, 20.0, 30.0, 30.0], [1, 2, 3, 4, 5], [])
    v, reason = compute_multiple(snap)
    assert reason == ""
    assert round(v, 4) == 10.0


def test_compute_multiple_ocf_non_positive():
    snap = _snapshot(1000.0, [20.0, -20.0, 0.0, 0.0], [1, 2, 3, 4, 5], [])
    v, reason = compute_multiple(snap)
    assert v is None
    assert reason == "OCF<=0"


def test_compute_multiple_ttm_fallback():
    snap = _snapshot(1400.0, [200.0, 100.0], [1, 2, 3, 4, 5], [], ocf_ttm=100.0)
    v, reason = compute_multiple(snap)
    assert reason == ""
    assert round(v, 4) == 14.0


def test_sales_trend_labels():
    assert classify_sales_trend([100, 110, 130, 160, 200]) in {"우상향", "횡보"}
    assert classify_sales_trend([200, 180, 160, 150, 130]) in {"우하향", "횡보"}
    assert classify_sales_trend([100, 100, 100, 100, 100]) == "횡보"
    assert classify_sales_trend([100, 101, 102, 103]) == "판정불가"


def test_evaluate_vip_boolean():
    prices = np.linspace(150, 100, 400).tolist()
    assert isinstance(evaluate_vip(prices), bool)
