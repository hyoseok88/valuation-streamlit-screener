from dataclasses import dataclass
from datetime import datetime


@dataclass
class UniverseRecord:
    symbol: str
    name: str
    country: str
    sector: str
    currency: str


@dataclass
class FundamentalSnapshot:
    market_cap: float | None
    ocf_q: list[float]
    revenue_y: list[float]
    asof_date: datetime
    sector: str
    currency: str
    price_series: list[float]


@dataclass
class ComputedSignal:
    multiple: float | None
    is_recommended: bool
    sales_trend: str
    vip_pass: bool
    rejection_reason: str
