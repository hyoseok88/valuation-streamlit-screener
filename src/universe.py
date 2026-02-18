from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import COUNTRY_SEED_FILES
from .models import UniverseRecord


def _normalize_symbol(country: str, symbol: str) -> str:
    symbol = str(symbol).strip().upper()
    if country == "KR_TOP200" and symbol.isdigit() and len(symbol) == 6:
        return f"{symbol}.KS"
    if country == "JP_TOP200" and symbol.isdigit():
        return f"{symbol}.T"
    if country == "US_TOP500":
        return symbol.replace(".", "-")
    return symbol


def _load_seed(country: str) -> list[dict[str, str]]:
    seed_path = Path(COUNTRY_SEED_FILES[country])
    if not seed_path.exists():
        return []
    df = pd.read_csv(seed_path)
    out = []
    for _, row in df.iterrows():
        out.append(
            {
                "symbol": _normalize_symbol(country, row.get("symbol", "")),
                "name": str(row.get("name", "")).strip(),
            }
        )
    return [x for x in out if x["symbol"]]


def _fetch_wiki_table(url: str, symbol_col: str, name_col: str) -> list[dict[str, str]]:
    try:
        tables = pd.read_html(url)
    except Exception:
        return []
    for table in tables:
        if symbol_col in table.columns and name_col in table.columns:
            result = []
            for _, row in table.iterrows():
                result.append({"symbol": str(row[symbol_col]).strip(), "name": str(row[name_col]).strip()})
            return result
    return []


def _wiki_candidates(country: str) -> list[dict[str, str]]:
    if country == "US_TOP500":
        return _fetch_wiki_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol", "Security")
    if country == "JP_TOP200":
        items = _fetch_wiki_table("https://en.wikipedia.org/wiki/Nikkei_225", "Ticker", "Company Name")
        for item in items:
            item["symbol"] = _normalize_symbol(country, item["symbol"])
        return items
    if country == "EU_TOP200":
        return _fetch_wiki_table("https://en.wikipedia.org/wiki/STOXX_Europe_600", "Ticker", "Company")
    return []


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


def _kr_top_from_fdr(n: int) -> list[UniverseRecord]:
    try:
        import FinanceDataReader as fdr

        listed = fdr.StockListing("KRX")
    except Exception:
        return []

    if listed is None or listed.empty:
        return []

    work = listed.copy()
    work["Code"] = work["Code"].astype(str).str.zfill(6)
    work["Marcap"] = pd.to_numeric(work.get("Marcap"), errors="coerce")
    work = work.dropna(subset=["Marcap"]).sort_values("Marcap", ascending=False).head(n)

    return [
        UniverseRecord(
            symbol=f"{row['Code']}.KS",
            name=str(row.get("Name", row["Code"])),
            country="KR_TOP200",
            sector="Unknown",
            currency="KRW",
        )
        for _, row in work.iterrows()
    ]


def get_top_universe(country: str, n: int) -> list[UniverseRecord]:
    from .market_data import fetch_overview_batch

    # KRX는 FDR의 Marcap 컬럼으로 Top N을 직접 뽑아 표본 누락을 최소화한다.
    if country == "KR_TOP200":
        kr_rows = _kr_top_from_fdr(n)
        if kr_rows:
            return kr_rows

    candidates = _merge_candidates(country, _load_seed(country), _wiki_candidates(country))

    symbols = [x["symbol"] for x in candidates]
    overview = fetch_overview_batch(symbols)

    rows = []
    for item in candidates:
        info = overview.get(item["symbol"], {})
        mcap = info.get("market_cap")
        rows.append(
            {
                "symbol": item["symbol"],
                "name": item["name"] or info.get("name", item["symbol"]),
                "sector": info.get("sector", "Unknown"),
                "currency": info.get("currency", "N/A"),
                "market_cap": float(mcap) if mcap else None,
            }
        )

    rows = sorted(rows, key=lambda x: (x["market_cap"] is not None, x["market_cap"] or 0.0), reverse=True)[:n]

    return [
        UniverseRecord(
            symbol=row["symbol"],
            name=row["name"],
            country=country,
            sector=row["sector"],
            currency=row["currency"],
        )
        for row in rows
    ]
