from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from .market_data import fetch_overview_batch
from .screens import normalize_ticker_input


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except Exception:
        return None
    if pd.isna(num):
        return None
    return num


def _safe_history(ticker: yf.Ticker, period: str, interval: str) -> pd.DataFrame:
    try:
        out = ticker.history(period=period, interval=interval, auto_adjust=False)
    except Exception:
        return pd.DataFrame()
    return out if isinstance(out, pd.DataFrame) else pd.DataFrame()


def _normalize_daily_history(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume", "TradingValue"])
    if not isinstance(history.index, pd.DatetimeIndex):
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume", "TradingValue"])

    daily = history.copy()
    if daily.index.tz is not None:
        daily.index = daily.index.tz_localize(None)

    keep = ["Open", "High", "Low", "Close", "Volume"]
    for col in keep:
        if col not in daily.columns:
            daily[col] = pd.NA
        daily[col] = pd.to_numeric(daily[col], errors="coerce")
    daily = daily[keep].dropna(subset=["Open", "High", "Low", "Close"])
    daily["Volume"] = daily["Volume"].fillna(0.0)
    daily["TradingValue"] = (daily["Close"] * daily["Volume"]).fillna(0.0)
    return daily


def resample_daily_to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    if daily is None or daily.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume", "TradingValue"])
    if not isinstance(daily.index, pd.DatetimeIndex):
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume", "TradingValue"])

    weekly = pd.DataFrame(
        {
            "Open": daily["Open"].resample("W-FRI").first(),
            "High": daily["High"].resample("W-FRI").max(),
            "Low": daily["Low"].resample("W-FRI").min(),
            "Close": daily["Close"].resample("W-FRI").last(),
            "Volume": daily["Volume"].resample("W-FRI").sum(min_count=1),
            "TradingValue": daily["TradingValue"].resample("W-FRI").sum(min_count=1),
        }
    )
    weekly = weekly.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    weekly["MA52"] = weekly["Close"].rolling(window=52, min_periods=52).mean()
    return weekly


def find_latest_weekly_breakout(weekly: pd.DataFrame) -> pd.Timestamp | None:
    if weekly is None or weekly.empty:
        return None
    if "Close" not in weekly.columns or "MA52" not in weekly.columns:
        return None
    close = pd.to_numeric(weekly["Close"], errors="coerce")
    ma52 = pd.to_numeric(weekly["MA52"], errors="coerce")

    valid = close.notna() & ma52.notna() & close.shift(1).notna() & ma52.shift(1).notna()
    cross_up = (close > ma52) & (close.shift(1) <= ma52.shift(1)) & valid
    if not cross_up.any():
        return None
    return weekly.index[cross_up][-1]


def _format_breakout_week(week_end: pd.Timestamp | None) -> str | None:
    if week_end is None:
        return None
    iso_week = int(week_end.isocalendar().week)
    return f"{week_end.year}-{week_end.month:02d}-{iso_week:02d}"


def build_target_price_base(country: str, ticker_input: str) -> dict[str, Any] | None:
    symbol = normalize_ticker_input(country, ticker_input)
    if not symbol:
        return None

    ticker = yf.Ticker(symbol)
    daily_hist = _normalize_daily_history(_safe_history(ticker, period="10y", interval="1d"))
    if daily_hist.empty:
        return {
            "symbol": symbol,
            "name": symbol,
            "currency": "N/A",
            "market_cap": None,
            "error": "Failed to fetch daily price history.",
        }

    weekly = resample_daily_to_weekly(daily_hist)
    if weekly.empty:
        return {
            "symbol": symbol,
            "name": symbol,
            "currency": "N/A",
            "market_cap": None,
            "error": "Failed to build weekly OHLCV data.",
        }

    overview = fetch_overview_batch([symbol]).get(symbol, {})
    name = overview.get("name") or symbol
    currency = overview.get("currency") or "N/A"
    market_cap = _safe_float(overview.get("market_cap"))
    current_price = _safe_float(daily_hist["Close"].iloc[-1]) if not daily_hist.empty else None
    ma52_price = _safe_float(weekly["MA52"].iloc[-1]) if not weekly.empty else None

    breakout_ts = find_latest_weekly_breakout(weekly)
    breakout_price = _safe_float(weekly.loc[breakout_ts, "Close"]) if breakout_ts is not None else None
    breakout_trading_value = (
        _safe_float(weekly.loc[breakout_ts, "TradingValue"]) if breakout_ts is not None else None
    )

    return {
        "symbol": symbol,
        "name": name,
        "currency": currency,
        "market_cap": market_cap,
        "current_price": current_price,
        "ma52_price": ma52_price,
        "weekly_frame": weekly,
        "breakout_week_end": breakout_ts,
        "breakout_week": _format_breakout_week(breakout_ts),
        "breakout_price": breakout_price,
        "breakout_trading_value": breakout_trading_value,
        "error": None,
    }


def apply_target_price_formula(base: dict[str, Any], float_rate_pct: float, multiplier: float) -> dict[str, Any]:
    result = dict(base)
    result["float_rate_pct"] = float_rate_pct
    result["multiplier"] = multiplier
    result["floating_cap"] = None
    result["energy_ratio"] = None
    result["target_price"] = None
    result["upside_pct"] = None

    if result.get("error"):
        return result

    market_cap = _safe_float(result.get("market_cap"))
    breakout_price = _safe_float(result.get("breakout_price"))
    breakout_trading_value = _safe_float(result.get("breakout_trading_value"))
    current_price = _safe_float(result.get("current_price"))

    float_rate = max(1.0, min(100.0, _safe_float(float_rate_pct) or 100.0))
    weight = max(0.1, min(5.0, _safe_float(multiplier) or 1.0))

    floating_cap = None
    if market_cap is not None and market_cap > 0:
        floating_cap = market_cap * (float_rate / 100.0)
    result["floating_cap"] = floating_cap

    energy_ratio = None
    if floating_cap is not None and floating_cap > 0 and breakout_trading_value is not None:
        energy_ratio = breakout_trading_value / floating_cap
    result["energy_ratio"] = energy_ratio

    target_price = None
    if breakout_price is not None and energy_ratio is not None:
        target_price = breakout_price * (1.0 + (energy_ratio * weight))
    result["target_price"] = target_price

    upside_pct = None
    if target_price is not None and current_price is not None and current_price > 0:
        upside_pct = (target_price / current_price - 1.0) * 100.0
    result["upside_pct"] = upside_pct

    if result.get("breakout_week_end") is None:
        result["error"] = "No weekly close breakout above MA52 was found."
    elif floating_cap is None:
        result["error"] = "Market cap is unavailable, so energy ratio cannot be calculated."

    return result
