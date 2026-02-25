from __future__ import annotations

import pandas as pd

from src.target_price import apply_target_price_formula, find_latest_weekly_breakout, resample_daily_to_weekly


def test_resample_daily_to_weekly_sums_trading_value() -> None:
    idx = pd.to_datetime(
        [
            "2025-01-06",
            "2025-01-07",
            "2025-01-08",
            "2025-01-09",
            "2025-01-10",
            "2025-01-13",
            "2025-01-14",
            "2025-01-15",
            "2025-01-16",
            "2025-01-17",
        ]
    )
    daily = pd.DataFrame(
        {
            "Open": [10.0] * 10,
            "High": [12.0] * 10,
            "Low": [9.0] * 10,
            "Close": [11.0] * 10,
            "Volume": [100.0] * 10,
            "TradingValue": [1100.0] * 10,
        },
        index=idx,
    )

    weekly = resample_daily_to_weekly(daily)

    assert len(weekly) == 2
    assert weekly.iloc[0]["TradingValue"] == 5500.0
    assert weekly.iloc[1]["TradingValue"] == 5500.0
    assert "MA52" in weekly.columns


def test_find_latest_weekly_breakout_by_weekly_close() -> None:
    idx = pd.date_range("2024-01-05", periods=60, freq="W-FRI")
    close = [100.0] * 58 + [99.0, 130.0]
    weekly = pd.DataFrame({"Close": close}, index=idx)
    weekly["MA52"] = weekly["Close"].rolling(window=52, min_periods=52).mean()

    breakout = find_latest_weekly_breakout(weekly)

    assert breakout == idx[-1]


def test_apply_target_price_formula_uses_user_float_rate() -> None:
    base = {
        "symbol": "TEST",
        "name": "TEST",
        "currency": "KRW",
        "market_cap": 1_000_000.0,
        "current_price": 10_000.0,
        "ma52_price": 9_500.0,
        "weekly_frame": pd.DataFrame(),
        "breakout_week_end": pd.Timestamp("2025-01-10"),
        "breakout_week": "2025-01-02",
        "breakout_price": 9_800.0,
        "breakout_trading_value": 200_000.0,
        "error": None,
    }

    result = apply_target_price_formula(base, float_rate_pct=20.0, multiplier=2.0)

    assert result["floating_cap"] == 200_000.0
    assert result["energy_ratio"] == 1.0
    assert result["target_price"] == 29_400.0
    assert round(result["upside_pct"], 2) == 194.0
