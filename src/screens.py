from __future__ import annotations

import pandas as pd

from .config import COUNTRY_LIMITS
from .market_data import fetch_snapshot
from .metrics import evaluate_snapshot
from .universe import get_top_universe


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
            continue
        signal = evaluate_snapshot(snap)
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

    df["_rec_sort"] = df["is_recommended"].astype(int)
    df = df.sort_values(by=["_rec_sort", "market_cap"], ascending=[False, False]).drop(columns=["_rec_sort"])
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
