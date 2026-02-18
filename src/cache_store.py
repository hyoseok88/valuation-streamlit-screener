import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import CACHE_DATE_FILE, CACHE_DIR, CACHE_VERSION


def _cache_path(country: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{country.lower()}_{CACHE_VERSION}.pkl"


def save_country_frame(country: str, df: pd.DataFrame) -> None:
    path = _cache_path(country)
    df.to_pickle(path)


def load_country_frame(country: str) -> pd.DataFrame | None:
    path = _cache_path(country)
    if not path.exists():
        return None
    return pd.read_pickle(path)


def save_meta(updates: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta = load_meta()
    meta.update(updates)
    meta["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    CACHE_DATE_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_meta() -> dict[str, str]:
    if not CACHE_DATE_FILE.exists():
        return {}
    return json.loads(CACHE_DATE_FILE.read_text(encoding="utf-8"))
