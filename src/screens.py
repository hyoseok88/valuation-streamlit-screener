from __future__ import annotations

import pandas as pd

from .config import COUNTRY_LIMITS, COUNTRY_SEED_FILES
from .market_data import fetch_overview_batch, fetch_snapshot
from .metrics import evaluate_snapshot
from .universe import get_top_universe


def _norm_token(text: str) -> str:
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())


def _resolve_alias_by_seed(country: str, ticker: str) -> str:
    key = _norm_token(ticker)
    if not key:
        return ticker
    path = COUNTRY_SEED_FILES.get(country)
    if not path:
        return ticker
    try:
        df = pd.read_csv(path, dtype={"symbol": str}, keep_default_na=False)
    except Exception:
        return ticker
    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).strip().upper()
        name = str(row.get("name", "")).strip()
        if not sym:
            continue
        base = sym.split(".")[0]
        if key in {_norm_token(sym), _norm_token(base), _norm_token(name)}:
            return sym
        if key and key in _norm_token(name):
            return sym
    return ticker


def _resolve_alias_by_universe(country: str, ticker: str) -> str:
    key = _norm_token(ticker)
    if not key:
        return ticker
    try:
        universe = get_top_universe(country, COUNTRY_LIMITS[country])
    except Exception:
        return ticker

    for item in universe:
        sym = (item.symbol or "").upper()
        base = sym.split(".")[0]
        name = _norm_token(item.name or "")
        if key == _norm_token(sym) or key == _norm_token(base) or key == name:
            return sym
        if key and (key in name):
            return sym
    return ticker


def normalize_ticker_input(country: str, ticker_input: str) -> str:
    ticker = (ticker_input or "").strip().upper()
    if not ticker:
        return ""
    if country == "KR_TOP200":
        if ticker.endswith(".KS"):
            return ticker
        digits = "".join(ch for ch in ticker if ch.isdigit())
        if digits and len(digits) <= 6:
            return f"{digits.zfill(6)}.KS"
        seeded = _resolve_alias_by_seed(country, ticker)
        if seeded != ticker:
            return normalize_ticker_input(country, seeded)
        return _resolve_alias_by_universe(country, ticker)
    if country == "JP_TOP200":
        if ticker.isdigit():
            return f"{ticker}.T"
        seeded = _resolve_alias_by_seed(country, ticker)
        if seeded != ticker:
            return seeded
        return _resolve_alias_by_universe(country, ticker)
    if country == "US_TOP500":
        seeded = _resolve_alias_by_seed(country, ticker)
        if seeded != ticker:
            return seeded.replace(".", "-")
        return ticker.replace(".", "-") if "." in ticker else _resolve_alias_by_universe(country, ticker)
    if country == "EU_TOP200":
        if "." in ticker:
            return ticker
        seeded = _resolve_alias_by_seed(country, ticker)
        if seeded != ticker:
            return seeded
        return _resolve_alias_by_universe(country, ticker)
    return _resolve_alias_by_universe(country, ticker)


def build_single_ticker_result(country: str, ticker_input: str) -> dict | None:
    symbol = normalize_ticker_input(country, ticker_input)
    if not symbol:
        return None

    snap = fetch_snapshot([symbol], country).get(symbol)
    if snap is None:
        return {
            "symbol": symbol,
            "name": symbol,
            "multiple": None,
            "vip_pass": False,
            "is_recommended": False,
            "strong_recommend": False,
            "sales_trend": "판정불가",
            "rejection_reason": "조회 실패",
            "market_cap": None,
            "currency": "N/A",
        }

    overview = fetch_overview_batch([symbol]).get(symbol, {})
    if snap.market_cap is None:
        mcap = overview.get("market_cap")
        snap.market_cap = float(mcap) if mcap else None
    if snap.currency == "N/A" and overview.get("currency"):
        snap.currency = overview["currency"]

    signal = evaluate_snapshot(snap)
    strong_recommend = (
        signal.sales_trend == "우상향"
        and signal.multiple is not None
        and float(signal.multiple) <= 10.0
    )
    return {
        "symbol": symbol,
        "name": overview.get("name") or symbol,
        "multiple": signal.multiple,
        "vip_pass": signal.vip_pass,
        "is_recommended": signal.is_recommended,
        "strong_recommend": bool(strong_recommend),
        "sales_trend": signal.sales_trend,
        "rejection_reason": signal.rejection_reason,
        "market_cap": snap.market_cap,
        "currency": snap.currency,
    }


def build_recommendations(country: str, filters: dict | None = None) -> pd.DataFrame:
    filters = filters or {}
    n = COUNTRY_LIMITS[country]

    universe = get_top_universe(country, n)
    symbols = [u.symbol for u in universe]
    snapshots = fetch_snapshot(symbols, country)

    rows = []
    for item in universe:
        snap = snapshots.get(item.symbol)
        if snap is None:
            rows.append(
                {
                    "country": country,
                    "symbol": item.symbol,
                    "name": item.name,
                    "sector": item.sector or "Unknown",
                    "currency": item.currency or "N/A",
                    "market_cap": None,
                    "multiple": None,
                    "is_recommended": False,
                    "strong_recommend": False,
                    "sales_trend": "판정불가",
                    "vip_pass": False,
                    "rejection_reason": "조회 실패",
                    "asof_date": None,
                }
            )
            continue
        signal = evaluate_snapshot(snap)
        strong_recommend = (
            signal.sales_trend == "우상향"
            and signal.multiple is not None
            and float(signal.multiple) <= 10.0
        )
        rows.append(
            {
                "country": country,
                "symbol": item.symbol,
                "name": item.name,
                "sector": snap.sector or item.sector,
                "currency": snap.currency or item.currency,
                "market_cap": snap.market_cap,
                "multiple": signal.multiple,
                "is_recommended": signal.is_recommended,
                "strong_recommend": bool(strong_recommend),
                "sales_trend": signal.sales_trend,
                "vip_pass": signal.vip_pass,
                "rejection_reason": signal.rejection_reason,
                "asof_date": snap.asof_date,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = apply_filters(df, filters)

    df["_strong_sort"] = df.get("strong_recommend", False).astype(int)
    df["_rec_sort"] = df["is_recommended"].astype(int)
    df = df.sort_values(
        by=["_strong_sort", "_rec_sort", "market_cap"],
        ascending=[False, False, False],
    ).drop(columns=["_strong_sort", "_rec_sort"])
    return df.reset_index(drop=True)


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df.copy()

    sectors = filters.get("sectors") or []
    if sectors:
        out = out[out["sector"].isin(sectors)]

    mult_min = filters.get("multiple_min")
    mult_max = filters.get("multiple_max")
    if mult_min is not None:
        out = out[(out["multiple"].isna()) | (out["multiple"] >= float(mult_min))]
    if mult_max is not None:
        out = out[(out["multiple"].isna()) | (out["multiple"] <= float(mult_max))]

    if filters.get("vip_only"):
        out = out[out["vip_pass"]]

    keyword = (filters.get("keyword") or "").strip().lower()
    if keyword:
        out = out[
            out["symbol"].str.lower().str.contains(keyword, na=False)
            | out["name"].str.lower().str.contains(keyword, na=False)
        ]

    return out

