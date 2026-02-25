from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from src.cache_store import load_country_frame, load_meta, save_country_frame, save_meta
from src.config import (
    COUNTRY_LABELS,
    COUNTRY_LIMITS,
    TARGET_PRICE_DEFAULT_FLOAT_RATE,
    TARGET_PRICE_DEFAULT_MULTIPLIER,
)
from src.screens import apply_filters, build_recommendations, build_single_ticker_result
from src.target_price import apply_target_price_formula, build_target_price_base
from src.ui_components import (
    render_filters,
    render_hero,
    render_recommend_treemap,
    render_target_price_result,
    render_strong_recommendations,
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


@st.cache_data(show_spinner=False, ttl=60 * 10)
def _target_base(country: str, ticker_input: str):
    return build_target_price_base(country, ticker_input)


def _load_or_build(country: str, force_refresh: bool):
    if not force_refresh:
        cached = load_country_frame(country)
        if cached is not None and not cached.empty and "strong_recommend" in cached.columns:
            return cached, True

    fresh = _refresh_country(country)
    if not fresh.empty:
        save_country_frame(country, fresh)
        save_meta({country: datetime.now(timezone.utc).isoformat()})
    return fresh, False


def main() -> None:
    st.set_page_config(page_title="Undervalued Valuation Screener", layout="wide")
    st.markdown(inject_theme(), unsafe_allow_html=True)

    st.sidebar.title("메뉴")
    menu = st.sidebar.radio(
        "선택",
        options=[
            "저평가 종목 찾기",
            "검색종목 목표가 산출(Target Price Calculator)",
        ],
    )

    st.sidebar.title("시장 선택")
    country = st.sidebar.radio(
        "유니버스",
        options=list(COUNTRY_LIMITS.keys()),
        format_func=lambda x: COUNTRY_LABELS[x],
    )
    if menu == "검색종목 목표가 산출(Target Price Calculator)":
        st.sidebar.subheader("입력")
        ticker_input = st.sidebar.text_input("종목 코드/명", value="", placeholder="예: 005930, 삼성전자, AAPL")
        float_rate = st.sidebar.number_input(
            "유동비율 (%)",
            min_value=1.0,
            max_value=100.0,
            value=float(TARGET_PRICE_DEFAULT_FLOAT_RATE),
            step=1.0,
            help="반드시 이 입력값으로 유통 시가총액을 계산합니다.",
        )
        multiplier = st.sidebar.slider(
            "목표가 배수 (Multiplier)",
            min_value=0.1,
            max_value=5.0,
            value=float(TARGET_PRICE_DEFAULT_MULTIPLIER),
            step=0.1,
        )
        result = None
        if ticker_input.strip():
            with st.spinner("목표가를 계산하는 중입니다..."):
                base = _target_base(country, ticker_input)
                if base is not None:
                    result = apply_target_price_formula(base, float_rate, multiplier)
        render_target_price_result(result)
        return

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
    render_strong_recommendations(filtered)
    render_recommend_treemap(filtered)
    render_table(filtered)


if __name__ == "__main__":
    main()
