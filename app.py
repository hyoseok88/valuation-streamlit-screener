from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from src.cache_store import load_country_frame, load_meta, save_country_frame, save_meta
from src.config import COUNTRY_LABELS, COUNTRY_LIMITS
from src.screens import apply_filters, build_recommendations, build_single_ticker_result
from src.ui_components import (
    render_filters,
    render_hero,
    render_recommend_treemap,
    render_single_ticker_result,
    render_table,
)
from src.ui_theme import inject_theme


@st.cache_data(show_spinner=False, ttl=60 * 30)
def _refresh_country(country: str):
    return build_recommendations(country, filters={})


@st.cache_data(show_spinner=False, ttl=60 * 10)
def _lookup_ticker(country: str, ticker_input: str):
    return build_single_ticker_result(country, ticker_input)


def _load_or_build(country: str, force_refresh: bool):
    if not force_refresh:
        cached = load_country_frame(country)
        if cached is not None and not cached.empty:
            return cached, True

    fresh = _refresh_country(country)
    if not fresh.empty:
        save_country_frame(country, fresh)
        save_meta({country: datetime.now(timezone.utc).isoformat()})
    return fresh, False


def main() -> None:
    st.set_page_config(page_title="Undervalued Valuation Screener", layout="wide")
    st.markdown(inject_theme(), unsafe_allow_html=True)

    st.sidebar.title("시장 선택")
    country = st.sidebar.radio(
        "유니버스",
        options=list(COUNTRY_LIMITS.keys()),
        format_func=lambda x: COUNTRY_LABELS[x],
    )
    force_refresh = st.sidebar.button("데이터 새로고침")

    with st.spinner("데이터를 불러오는 중입니다..."):
        df, from_cache = _load_or_build(country, force_refresh)

    if df.empty:
        st.error("데이터를 가져오지 못했습니다. 시드 파일 또는 네트워크 상태를 확인하세요.")
        return

    filters = render_filters(df)
    filtered = apply_filters(df, filters)
    ticker_query = (filters.get("ticker_lookup") or "").strip()
    ticker_result = None
    if ticker_query:
        with st.spinner("개별 티커 지표를 조회하는 중입니다..."):
            ticker_result = _lookup_ticker(country, ticker_query)

    meta = load_meta()
    updated_at = meta.get(country) or meta.get("updated_at_utc") or "N/A"
    if from_cache:
        updated_at = f"{updated_at} (cache)"

    render_hero(COUNTRY_LABELS[country], updated_at, filtered)
    render_single_ticker_result(ticker_result)
    render_recommend_treemap(filtered)
    render_table(filtered)


if __name__ == "__main__":
    main()
