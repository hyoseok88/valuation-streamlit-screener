from dataclasses import dataclass, field
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
    ocf_ttm: float | None
    revenue_y: list[float]
    asof_date: datetime
    sector: str
    currency: str
    price_series: list[float]
    ocf_y: list[float] = field(default_factory=list)


@dataclass
class ComputedSignal:
    multiple: float | None
    is_recommended: bool
    sales_trend: str
    vip_pass: bool
    rejection_reason: str
