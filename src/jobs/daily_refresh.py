from __future__ import annotations

from datetime import datetime, timezone

from src.cache_store import save_country_frame, save_meta
from src.config import COUNTRY_LIMITS
from src.screens import build_recommendations


def main() -> None:
    status = {}
    for country in COUNTRY_LIMITS:
        df = build_recommendations(country, filters={})
        save_country_frame(country, df)
        status[country] = datetime.now(timezone.utc).isoformat()
    save_meta(status)


if __name__ == "__main__":
    main()
