from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

import pandas as pd
import yfinance as yf

from .models import FundamentalSnapshot

OCF_KEYS = [
    "Operating Cash Flow",
    "Total Cash From Operating Activities",
    "Cash Flow From Continuing Operating Activities",
    "OperatingCashFlow",
]

REVENUE_KEYS = [
    "Total Revenue",
    "Revenue",
    "Operating Revenue",
    "TotalRevenue",
]


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except Exception:
        return None
    if pd.isna(num):
        return None
    return num


def _series_to_float_list(series: pd.Series | None, max_len: int | None = None, newest_first: bool = True) -> list[float]:
    if series is None:
        return []
    work = series
    if isinstance(series.index, pd.DatetimeIndex):
        work = series.sort_index(ascending=not newest_first)
    vals = pd.to_numeric(work, errors="coerce").dropna().tolist()
    if max_len is None:
        return vals
    if newest_first:
        return vals[:max_len]
    return vals[-max_len:]


def _pick_row(df: pd.DataFrame | None, keys: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for key in keys:
        if key in df.index:
            selected = df.loc[key]
            return selected.iloc[0] if isinstance(selected, pd.DataFrame) else selected
    for idx in df.index:
        idx_text = str(idx).lower()
        if any(key.lower().replace(" ", "") in idx_text.replace(" ", "") for key in keys):
            selected = df.loc[idx]
            return selected.iloc[0] if isinstance(selected, pd.DataFrame) else selected
    return None


@lru_cache(maxsize=1)
def _kr_marcap_map() -> dict[str, float]:
    try:
        import FinanceDataReader as fdr

        listed = fdr.StockListing("KRX")
    except Exception:
        return {}

    if listed is None or listed.empty:
        return {}

    out: dict[str, float] = {}
    for _, row in listed.iterrows():
        code = str(row.get("Code", "")).zfill(6)
        marcap = _safe_float(row.get("Marcap"))
        if code and marcap and marcap > 0:
            out[code] = marcap
    return out


def _extract_market_cap(ticker: yf.Ticker, info: dict, symbol: str, country: str) -> float | None:
    candidates = [
        info.get("marketCap"),
        info.get("market_cap"),
    ]
    try:
        fi = ticker.fast_info
        candidates.extend(
            [
                fi.get("market_cap"),
                fi.get("marketCap"),
                fi.get("market_capitalization"),
            ]
        )
    except Exception:
        pass

    for candidate in candidates:
        val = _safe_float(candidate)
        if val and val > 0:
            return val

    if country == "KR_TOP200":
        code = str(symbol).split(".")[0]
        fallback = _kr_marcap_map().get(code)
        if fallback and fallback > 0:
            return fallback
    return None


def _extract_ocf_data(ticker: yf.Ticker, info: dict) -> tuple[list[float], float | None]:
    q_cf = getattr(ticker, "quarterly_cashflow", pd.DataFrame())
    q_row = _pick_row(q_cf, OCF_KEYS)
    ocf_q = _series_to_float_list(q_row, max_len=4, newest_first=True)

    ocf_ttm = _safe_float(info.get("operatingCashflow"))
    if ocf_ttm is None:
        annual_cf = getattr(ticker, "cashflow", pd.DataFrame())
        a_row = _pick_row(annual_cf, OCF_KEYS)
        annual_vals = _series_to_float_list(a_row, max_len=1, newest_first=True)
        if annual_vals:
            ocf_ttm = annual_vals[0]

    # 분기 1~3개만 있을 경우 연환산으로 보수적 대체값 생성
    if ocf_ttm is None and len(ocf_q) >= 2:
        ocf_ttm = float(sum(ocf_q)) * (4.0 / float(len(ocf_q)))

    return ocf_q, ocf_ttm


def _extract_revenue_yearly(ticker: yf.Ticker) -> list[float]:
    annual_fin = getattr(ticker, "financials", pd.DataFrame())
    annual_row = _pick_row(annual_fin, REVENUE_KEYS)
    revenue = _series_to_float_list(annual_row, max_len=5, newest_first=False)
    if revenue:
        return revenue

    income_stmt = getattr(ticker, "income_stmt", pd.DataFrame())
    income_row = _pick_row(income_stmt, REVENUE_KEYS)
    revenue = _series_to_float_list(income_row, max_len=5, newest_first=False)
    if revenue:
        return revenue

    q_income = getattr(ticker, "quarterly_income_stmt", pd.DataFrame())
    q_row = _pick_row(q_income, REVENUE_KEYS)
    if q_row is None:
        return []
    q_series = pd.to_numeric(q_row, errors="coerce").dropna()
    if q_series.empty or not isinstance(q_series.index, pd.DatetimeIndex):
        return []
    q_series = q_series.sort_index()
    y_series = q_series.groupby(q_series.index.year).sum().sort_index()
    return [float(v) for v in y_series.tolist()][-5:]


def fetch_overview_batch(symbols: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            market_cap = _extract_market_cap(ticker, info, symbol, country="")
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
            info = ticker.info or {}

            market_cap = _extract_market_cap(ticker, info, symbol, country)
            ocf_q, ocf_ttm = _extract_ocf_data(ticker, info)
            revenue_y = _extract_revenue_yearly(ticker)

            hist = ticker.history(period="18mo", interval="1d", auto_adjust=False)
            price_series = (
                pd.to_numeric(hist["Close"], errors="coerce").dropna().astype(float).tolist() if not hist.empty else []
            )

            sector = info.get("sector") or "Unknown"
            currency = info.get("currency")
            if not currency:
                try:
                    currency = ticker.fast_info.get("currency")
                except Exception:
                    currency = None

            snapshots[symbol] = FundamentalSnapshot(
                market_cap=market_cap,
                ocf_q=ocf_q,
                ocf_ttm=ocf_ttm,
                revenue_y=revenue_y,
                asof_date=datetime.now(timezone.utc),
                sector=sector,
                currency=currency or "N/A",
                price_series=price_series,
            )
        except Exception:
            snapshots[symbol] = FundamentalSnapshot(
                market_cap=None,
                ocf_q=[],
                ocf_ttm=None,
                revenue_y=[],
                asof_date=datetime.now(timezone.utc),
                sector="Unknown",
                currency="N/A",
                price_series=[],
            )

    return snapshots
