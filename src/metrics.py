from __future__ import annotations

import math

import numpy as np

from .config import (
    MA_LONG,
    MA_SHORT,
    MULTIPLE_THRESHOLD,
    SALES_R2_FLAT,
    SALES_SLOPE_EPS,
    SIX_MONTH_TRADING_DAYS,
    VIP_BELOW_RATIO,
)
from .models import ComputedSignal, FundamentalSnapshot


def _r2_score(y: np.ndarray, yhat: np.ndarray) -> float:
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    if ss_tot == 0:
        return 0.0
    return 1 - (ss_res / ss_tot)


def compute_multiple(snapshot: FundamentalSnapshot) -> tuple[float | None, str]:
    if snapshot.market_cap is None:
        return None, "데이터 부족"
    if len(snapshot.ocf_q) < 4:
        return None, "OCF 데이터 부족"

    ocf_sum = float(np.nansum(snapshot.ocf_q[:4]))
    if ocf_sum <= 0:
        return None, "OCF<=0"

    return float(snapshot.market_cap) / ocf_sum, ""


def classify_sales_trend(revenue_5y: list[float]) -> str:
    vals = [float(v) for v in revenue_5y if v is not None and not math.isnan(float(v))]
    if len(vals) <= 4:
        return "판정불가"

    y = np.array(vals[:5], dtype=float)
    x = np.arange(len(y), dtype=float)

    slope, intercept = np.polyfit(x, y, 1)
    yhat = slope * x + intercept
    r2 = _r2_score(y, yhat)

    scale = max(np.mean(np.abs(y)), 1.0)
    norm_slope = slope / scale

    if r2 < SALES_R2_FLAT or abs(norm_slope) <= SALES_SLOPE_EPS:
        return "횡보"
    if norm_slope > 0:
        return "우상향"
    return "우하향"


def evaluate_vip(price_series: list[float]) -> bool:
    if len(price_series) < MA_LONG + SIX_MONTH_TRADING_DAYS:
        return False

    arr = np.array(price_series, dtype=float)
    ma112 = np.convolve(arr, np.ones(MA_SHORT) / MA_SHORT, mode="valid")
    ma224 = np.convolve(arr, np.ones(MA_LONG) / MA_LONG, mode="valid")

    ma112_full = np.concatenate([np.full(MA_SHORT - 1, np.nan), ma112])
    ma224_full = np.concatenate([np.full(MA_LONG - 1, np.nan), ma224])

    close_now = arr[-1]
    ma112_now = ma112_full[-1]
    ma224_now = ma224_full[-1]
    if np.isnan(ma112_now) or np.isnan(ma224_now):
        return False

    cond1 = close_now < ma224_now
    cond3 = ma112_now < ma224_now
    cond4 = (close_now > ma112_now) and (close_now < ma224_now)

    six_month_close = arr[-SIX_MONTH_TRADING_DAYS:]
    six_month_ma224 = ma224_full[-SIX_MONTH_TRADING_DAYS:]
    valid = ~np.isnan(six_month_ma224)
    if valid.sum() == 0:
        return False
    ratio = float((six_month_close[valid] < six_month_ma224[valid]).sum()) / float(valid.sum())
    cond2 = ratio >= VIP_BELOW_RATIO

    return bool(cond1 and cond2 and cond3 and cond4)


def evaluate_snapshot(snapshot: FundamentalSnapshot) -> ComputedSignal:
    multiple, reason = compute_multiple(snapshot)
    trend = classify_sales_trend(snapshot.revenue_y)
    vip_pass = evaluate_vip(snapshot.price_series)
    is_recommended = multiple is not None and multiple <= MULTIPLE_THRESHOLD
    if not is_recommended and not reason:
        reason = f"멀티플>{MULTIPLE_THRESHOLD:g}"
    return ComputedSignal(
        multiple=multiple,
        is_recommended=is_recommended,
        sales_trend=trend,
        vip_pass=vip_pass,
        rejection_reason=reason,
    )

