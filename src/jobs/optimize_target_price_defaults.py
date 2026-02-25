from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import time

import numpy as np
import pandas as pd
import yfinance as yf

from src.config import COUNTRY_SEED_FILES
from src.market_data import fetch_overview_batch
from src.screens import normalize_ticker_input
from src.target_price import _normalize_daily_history, resample_daily_to_weekly


@dataclass
class EventRow:
    symbol: str
    breakout_date: pd.Timestamp
    breakout_price: float
    breakout_trading_value: float
    market_cap: float
    future_max_high: float


def _detect_breakout_rows(weekly: pd.DataFrame, market_cap: float, horizon_weeks: int) -> list[EventRow]:
    if weekly.empty or market_cap <= 0:
        return []

    work = weekly.copy()
    work["MA52"] = pd.to_numeric(work["MA52"], errors="coerce")
    work["Close"] = pd.to_numeric(work["Close"], errors="coerce")
    work["High"] = pd.to_numeric(work["High"], errors="coerce")
    work["TradingValue"] = pd.to_numeric(work["TradingValue"], errors="coerce")
    work = work.dropna(subset=["Close", "MA52", "High", "TradingValue"])
    if work.empty:
        return []

    rows: list[EventRow] = []
    close = work["Close"]
    ma52 = work["MA52"]
    cross_up = (
        (close > ma52)
        & (close.shift(1) <= ma52.shift(1))
        & close.shift(1).notna()
        & ma52.shift(1).notna()
    )
    breakout_idx = list(work.index[cross_up])
    if not breakout_idx:
        return []

    for ts in breakout_idx:
        i = work.index.get_loc(ts)
        if isinstance(i, slice):
            continue
        end = min(i + horizon_weeks, len(work) - 1)
        if end <= i:
            continue
        future_high = float(work.iloc[i + 1 : end + 1]["High"].max())
        if not np.isfinite(future_high):
            continue
        breakout_price = float(work.iloc[i]["Close"])
        trading_value = float(work.iloc[i]["TradingValue"])
        if breakout_price <= 0 or trading_value <= 0:
            continue
        rows.append(
            EventRow(
                symbol="",
                breakout_date=ts,
                breakout_price=breakout_price,
                breakout_trading_value=trading_value,
                market_cap=float(market_cap),
                future_max_high=future_high,
            )
        )
    return rows


def _load_symbols(country: str, max_symbols: int) -> list[str]:
    path = COUNTRY_SEED_FILES[country]
    seed = pd.read_csv(path, dtype={"symbol": str}, keep_default_na=False)
    symbols = [
        normalize_ticker_input(country, str(raw).strip())
        for raw in seed["symbol"].tolist()
        if str(raw).strip()
    ]
    deduped = []
    seen = set()
    for sym in symbols:
        if not sym or sym in seen:
            continue
        deduped.append(sym)
        seen.add(sym)
    return deduped[:max_symbols]


def build_event_frame(
    country: str,
    max_symbols: int,
    start: str,
    end: str,
    horizon_weeks: int,
    pause: float,
) -> pd.DataFrame:
    symbols = _load_symbols(country, max_symbols=max_symbols)
    market_caps = fetch_overview_batch(symbols)

    rows: list[dict] = []
    for idx, symbol in enumerate(symbols, start=1):
        try:
            ticker = yf.Ticker(symbol)
            daily = _normalize_daily_history(ticker.history(start=start, end=end, interval="1d", auto_adjust=False))
            weekly = resample_daily_to_weekly(daily)
            mcap = market_caps.get(symbol, {}).get("market_cap")
            if mcap is None or float(mcap) <= 0:
                continue
            events = _detect_breakout_rows(weekly, market_cap=float(mcap), horizon_weeks=horizon_weeks)
            for event in events:
                rows.append(
                    {
                        "symbol": symbol,
                        "breakout_date": event.breakout_date,
                        "breakout_price": event.breakout_price,
                        "breakout_trading_value": event.breakout_trading_value,
                        "market_cap": event.market_cap,
                        "future_max_high": event.future_max_high,
                    }
                )
        except Exception:
            continue
        if pause > 0 and idx < len(symbols):
            time.sleep(pause)

    if not rows:
        return pd.DataFrame(
            columns=[
                "symbol",
                "breakout_date",
                "breakout_price",
                "breakout_trading_value",
                "market_cap",
                "future_max_high",
            ]
        )
    out = pd.DataFrame(rows)
    out["breakout_date"] = pd.to_datetime(out["breakout_date"])
    return out.sort_values("breakout_date").reset_index(drop=True)


def _evaluate_grid(
    events: pd.DataFrame,
    float_rates: list[float],
    multipliers: list[float],
    validation_start: str,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    df = events.copy()
    df["validation"] = df["breakout_date"] >= pd.Timestamp(validation_start)
    base_ratio = df["breakout_trading_value"] / df["market_cap"]

    records: list[dict] = []
    for float_rate in float_rates:
        float_factor = float_rate / 100.0
        if float_factor <= 0:
            continue
        energy = base_ratio / float_factor
        for mult in multipliers:
            target = df["breakout_price"] * (1.0 + energy * mult)
            hit = df["future_max_high"] >= target
            target_upside = (target / df["breakout_price"] - 1.0) * 100.0

            train_mask = ~df["validation"]
            valid_mask = df["validation"]
            train_n = int(train_mask.sum())
            valid_n = int(valid_mask.sum())
            if train_n == 0 or valid_n == 0:
                continue

            train_hit = float(hit[train_mask].mean())
            valid_hit = float(hit[valid_mask].mean())
            train_up = float(target_upside[train_mask].mean())
            valid_up = float(target_upside[valid_mask].mean())
            score = valid_hit * np.log1p(max(valid_up, 0.0))

            records.append(
                {
                    "float_rate": float_rate,
                    "multiplier": mult,
                    "train_events": train_n,
                    "valid_events": valid_n,
                    "train_hit_rate": train_hit,
                    "valid_hit_rate": valid_hit,
                    "train_avg_target_upside_pct": train_up,
                    "valid_avg_target_upside_pct": valid_up,
                    "valid_balanced_score": float(score),
                }
            )
    if not records:
        return pd.DataFrame()
    result = pd.DataFrame(records)
    return result.sort_values(
        by=["valid_hit_rate", "valid_balanced_score", "valid_avg_target_upside_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grid search default params for target price calculator")
    parser.add_argument("--country", default="KR_TOP200")
    parser.add_argument("--max-symbols", type=int, default=120)
    parser.add_argument("--start", default="2014-01-01")
    parser.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    parser.add_argument("--validation-start", default="2023-01-01")
    parser.add_argument("--horizon-weeks", type=int, default=26)
    parser.add_argument("--float-min", type=float, default=10.0)
    parser.add_argument("--float-max", type=float, default=100.0)
    parser.add_argument("--float-step", type=float, default=5.0)
    parser.add_argument("--mult-min", type=float, default=0.1)
    parser.add_argument("--mult-max", type=float, default=5.0)
    parser.add_argument("--mult-step", type=float, default=0.1)
    parser.add_argument("--pause", type=float, default=0.0)
    parser.add_argument("--out-json", default="data_cache/target_price_grid_search.json")
    parser.add_argument("--out-csv", default="data_cache/target_price_grid_search_table.csv")
    return parser.parse_args()


def _grid_values(min_v: float, max_v: float, step: float) -> list[float]:
    count = int(round((max_v - min_v) / step))
    vals = [round(min_v + step * i, 6) for i in range(count + 1)]
    return [v for v in vals if v <= max_v + 1e-9]


def main() -> None:
    args = parse_args()
    events = build_event_frame(
        country=args.country,
        max_symbols=args.max_symbols,
        start=args.start,
        end=args.end,
        horizon_weeks=args.horizon_weeks,
        pause=args.pause,
    )
    if events.empty:
        raise SystemExit("No events collected. Adjust symbols/date range.")

    float_rates = _grid_values(args.float_min, args.float_max, args.float_step)
    multipliers = _grid_values(args.mult_min, args.mult_max, args.mult_step)
    table = _evaluate_grid(
        events=events,
        float_rates=float_rates,
        multipliers=multipliers,
        validation_start=args.validation_start,
    )
    if table.empty:
        raise SystemExit("Grid search produced no rows.")

    best = table.iloc[0].to_dict()

    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_csv, index=False)

    payload = {
        "country": args.country,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "max_symbols": args.max_symbols,
            "start": args.start,
            "end": args.end,
            "validation_start": args.validation_start,
            "horizon_weeks": args.horizon_weeks,
            "float_grid": [args.float_min, args.float_max, args.float_step],
            "mult_grid": [args.mult_min, args.mult_max, args.mult_step],
        },
        "event_count": int(len(events)),
        "best": best,
        "top10": table.head(10).to_dict(orient="records"),
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
