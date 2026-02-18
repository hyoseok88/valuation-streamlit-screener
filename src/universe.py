from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from .config import COUNTRY_SEED_FILES
from .models import UniverseRecord


def _normalize_symbol(country: str, symbol: str) -> str:
    symbol = str(symbol).strip().upper()
    if country == "KR_TOP200" and symbol.isdigit():
        return f"{symbol.zfill(6)}.KS"
    if country == "JP_TOP200" and symbol.isdigit():
        return f"{symbol}.T"
    if country == "US_TOP500":
        return symbol.replace(".", "-")
    return symbol


def _load_seed(country: str) -> list[dict[str, str]]:
    seed_path = Path(COUNTRY_SEED_FILES[country])
    if not seed_path.exists():
        return []
    df = pd.read_csv(seed_path, dtype={"symbol": str}, keep_default_na=False)
    out = []
    for _, row in df.iterrows():
        out.append(
            {
                "symbol": _normalize_symbol(country, row.get("symbol", "")),
                "name": str(row.get("name", "")).strip(),
            }
        )
    return [x for x in out if x["symbol"]]


def _fetch_wiki_tables(url: str) -> list[pd.DataFrame]:
    try:
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
        return pd.read_html(StringIO(html))
    except Exception:
        return []


def _extract_symbol_name(table: pd.DataFrame) -> list[dict[str, str]]:
    cols = [str(c) for c in table.columns]
    col_map = {str(c).lower(): str(c) for c in table.columns}

    symbol_col = None
    for key in ["symbol", "ticker", "epic", "ric", "code"]:
        matched = [orig for lower, orig in col_map.items() if key in lower]
        if matched:
            symbol_col = matched[0]
            break
    if symbol_col is None:
        return []

    name_col = None
    for key in ["company", "security", "name"]:
        matched = [orig for lower, orig in col_map.items() if key in lower]
        if matched:
            name_col = matched[0]
            break
    if name_col is None:
        # Use second column as fallback.
        if len(cols) >= 2:
            name_col = cols[1]
        else:
            return []

    out = []
    for _, row in table.iterrows():
        symbol = str(row.get(symbol_col, "")).strip()
        name = str(row.get(name_col, "")).strip()
        if symbol and symbol.lower() != "nan":
            out.append({"symbol": symbol, "name": name})
    return out


def _merge_candidates(country: str, *candidate_lists: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for items in candidate_lists:
        for item in items:
            symbol = _normalize_symbol(country, item.get("symbol", ""))
            if not symbol:
                continue
            name = str(item.get("name", "")).strip()
            if symbol not in merged:
                merged[symbol] = {"symbol": symbol, "name": name}
            elif not merged[symbol]["name"] and name:
                merged[symbol]["name"] = name
    return list(merged.values())


def _kr_candidates_fdr() -> list[dict[str, str]]:
    try:
        import FinanceDataReader as fdr

        listed = fdr.StockListing("KRX")
    except Exception:
        return []
    if listed is None or listed.empty:
        return []
    out = []
    for _, row in listed.iterrows():
        code = str(row.get("Code", "")).zfill(6)
        if code.isdigit():
            out.append({"symbol": f"{code}.KS", "name": str(row.get("Name", code))})
    return out


def _us_candidates_fdr() -> list[dict[str, str]]:
    try:
        import FinanceDataReader as fdr

        listed = fdr.StockListing("S&P500")
    except Exception:
        return []
    if listed is None or listed.empty:
        return []
    out = []
    for _, row in listed.iterrows():
        out.append({"symbol": _normalize_symbol("US_TOP500", row.get("Symbol", "")), "name": str(row.get("Name", ""))})
    return [x for x in out if x["symbol"]]


def _jp_candidates_fdr() -> list[dict[str, str]]:
    try:
        import FinanceDataReader as fdr

        listed = fdr.StockListing("TSE")
    except Exception:
        return []
    if listed is None or listed.empty:
        return []
    out = []
    for _, row in listed.iterrows():
        symbol = str(row.get("Symbol", "")).strip()
        if symbol.isdigit():
            out.append({"symbol": f"{symbol}.T", "name": str(row.get("Name", symbol))})
    return out


def _eu_candidates_from_indexes() -> list[dict[str, str]]:
    urls = [
        "https://en.wikipedia.org/wiki/FTSE_100_Index",
        "https://en.wikipedia.org/wiki/DAX",
        "https://en.wikipedia.org/wiki/CAC_40",
        "https://en.wikipedia.org/wiki/AEX_index",
        "https://en.wikipedia.org/wiki/Swiss_Market_Index",
        "https://en.wikipedia.org/wiki/IBEX_35",
        "https://en.wikipedia.org/wiki/FTSE_MIB",
        "https://en.wikipedia.org/wiki/OMX_Stockholm_30",
    ]
    gathered: list[dict[str, str]] = []
    for url in urls:
        tables = _fetch_wiki_tables(url)
        for table in tables:
            extracted = _extract_symbol_name(table)
            if extracted:
                gathered.extend(extracted)
    return gathered


def get_top_universe(country: str, n: int) -> list[UniverseRecord]:
    if country == "KR_TOP200":
        # KR uses FDR market-cap ranking directly when available.
        try:
            import FinanceDataReader as fdr

            listed = fdr.StockListing("KRX")
            if listed is not None and not listed.empty:
                work = listed.copy()
                work["Code"] = work["Code"].astype(str).str.zfill(6)
                work["Marcap"] = pd.to_numeric(work.get("Marcap"), errors="coerce")
                work = work.dropna(subset=["Marcap"]).sort_values("Marcap", ascending=False).head(n)
                return [
                    UniverseRecord(
                        symbol=f"{row['Code']}.KS",
                        name=str(row.get("Name", row["Code"])),
                        country=country,
                        sector="Unknown",
                        currency="KRW",
                    )
                    for _, row in work.iterrows()
                ]
        except Exception:
            pass
        candidates = _merge_candidates(country, _load_seed(country))
    elif country == "US_TOP500":
        candidates = _merge_candidates(country, _us_candidates_fdr(), _load_seed(country))
    elif country == "JP_TOP200":
        candidates = _merge_candidates(country, _jp_candidates_fdr(), _load_seed(country))
    else:
        candidates = _merge_candidates(country, _eu_candidates_from_indexes(), _load_seed(country))

    rows = candidates[:n]

    return [
        UniverseRecord(
            symbol=row["symbol"],
            name=row.get("name", "") or row["symbol"],
            country=country,
            sector="Unknown",
            currency="N/A",
        )
        for row in rows
    ]
