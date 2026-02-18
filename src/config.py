from pathlib import Path

COUNTRY_LIMITS = {
    "KR_TOP200": 200,
    "US_TOP500": 500,
    "JP_TOP200": 200,
    "EU_TOP200": 200,
}

COUNTRY_LABELS = {
    "KR_TOP200": "Korea Top 200",
    "US_TOP500": "US Top 500",
    "JP_TOP200": "Japan Top 200",
    "EU_TOP200": "Europe Top 200",
}

COUNTRY_SEED_FILES = {
    "KR_TOP200": "seeds/kr_seed.csv",
    "US_TOP500": "seeds/us_seed.csv",
    "JP_TOP200": "seeds/jp_seed.csv",
    "EU_TOP200": "seeds/eu_seed.csv",
}

MULTIPLE_THRESHOLD = 14.0
MA_SHORT = 112
MA_LONG = 224
SIX_MONTH_TRADING_DAYS = 126
VIP_BELOW_RATIO = 2.0 / 3.0

SALES_SLOPE_EPS = 0.02
SALES_R2_FLAT = 0.35

CACHE_DIR = Path("data_cache")
CACHE_VERSION = "v1"
CACHE_DATE_FILE = CACHE_DIR / "cache_meta.json"

DEFAULT_MULTIPLE_RANGE = (0.0, 30.0)
CACHE_TTL_SECONDS = 60 * 60 * 24
