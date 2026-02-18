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
        items = _fetch_wiki_table(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol", "Security"
        )
        if items:
            return items
    if country == "JP_TOP200":
        items = _fetch_wiki_table("https://en.wikipedia.org/wiki/Nikkei_225", "Ticker", "Company Name")
        if items:
            for item in items:
                item["symbol"] = _normalize_symbol(country, item["symbol"])
            return items
    if country == "EU_TOP200":
        items = _fetch_wiki_table(
            "https://en.wikipedia.org/wiki/STOXX_Europe_600", "Ticker", "Company"
        )
        if items:
            return items
    return []


def get_top_universe(country: str, n: int) -> list[UniverseRecord]:
    from .market_data import fetch_overview_batch

    candidates = _load_seed(country)
    if not candidates:
        candidates = _wiki_candidates(country)

    if country == "KR_TOP200" and not candidates:
        try:
            import FinanceDataReader as fdr

            listed = fdr.StockListing("KRX")
            candidates = [
                {"symbol": _normalize_symbol(country, row["Code"]), "name": str(row.get("Name", ""))}
                for _, row in listed.iterrows()
                if str(row.get("Code", "")).isdigit()
            ]
        except Exception:
            candidates = []

    symbols = [x["symbol"] for x in candidates]
    overview = fetch_overview_batch(symbols)

    rows = []
    for item in candidates:
        info = overview.get(item["symbol"], {})
        mcap = info.get("market_cap")
        if not mcap:
            continue
        rows.append(
            {
                "symbol": item["symbol"],
                "name": item["name"] or info.get("name", item["symbol"]),
                "sector": info.get("sector", "Unknown"),
                "currency": info.get("currency", "N/A"),
                "market_cap": float(mcap),
            }
        )

    rows = sorted(rows, key=lambda x: x["market_cap"], reverse=True)[:n]

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
