from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from .models import FundamentalSnapshot


def _series_to_float_list(series: pd.Series | None, max_len: int | None = None, newest_first: bool = True) -> list[float]:
    if series is None:
        return []
    work = series
    if isinstance(series.index, pd.DatetimeIndex):
        work = series.sort_index(ascending=not newest_first)
    vals = pd.to_numeric(work, errors="coerce").dropna().tolist()
    return vals[:max_len] if max_len else vals


def _pick_row(df: pd.DataFrame | None, keys: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for key in keys:
        if key in df.index:
            return df.loc[key]
    for idx in df.index:
        if any(key.lower() in str(idx).lower() for key in keys):
            return df.loc[idx]
    return None


def fetch_overview_batch(symbols: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            market_cap = info.get("marketCap")
            if not market_cap:
                try:
                    market_cap = ticker.fast_info.get("market_cap")
                except Exception:
                    market_cap = None
            out[symbol] = {
                "market_cap": market_cap,
                "sector": info.get("sector") or "Unknown",
                "currency": info.get("currency") or "N/A",
                "name": info.get("shortName") or info.get("longName") or symbol,
            }
        except Exception:
            out[symbol] = {}
    return out


def fetch_snapshot(symbols: list[str], country: str) -> dict[str, FundamentalSnapshot]:
    snapshots: dict[str, FundamentalSnapshot] = {}

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            q_cf = getattr(ticker, "quarterly_cashflow", pd.DataFrame())
            ocf_row = _pick_row(q_cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
            ocf_q = _series_to_float_list(ocf_row, max_len=4, newest_first=True)

            fin = getattr(ticker, "financials", pd.DataFrame())
            rev_row = _pick_row(fin, ["Total Revenue", "Revenue"])
            revenue_y = _series_to_float_list(rev_row, max_len=5, newest_first=False)

            hist = ticker.history(period="18mo", interval="1d", auto_adjust=False)
            price_series = (
                pd.to_numeric(hist["Close"], errors="coerce").dropna().astype(float).tolist() if not hist.empty else []
            )

            snapshots[symbol] = FundamentalSnapshot(
                market_cap=info.get("marketCap"),
                ocf_q=ocf_q,
                revenue_y=revenue_y,
                asof_date=datetime.now(timezone.utc),
                sector=info.get("sector") or "Unknown",
                currency=info.get("currency") or "N/A",
                price_series=price_series,
            )
        except Exception:
            snapshots[symbol] = FundamentalSnapshot(
                market_cap=None,
                ocf_q=[],
                revenue_y=[],
                asof_date=datetime.now(timezone.utc),
                sector="Unknown",
                currency="N/A",
                price_series=[],
            )

    return snapshots

