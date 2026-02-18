from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


def render_hero(country_label: str, updated_at: str, df: pd.DataFrame) -> None:
    rec_count = int(df["is_recommended"].sum()) if not df.empty else 0
    med = float(df["multiple"].dropna().median()) if not df.empty and df["multiple"].notna().any() else float("nan")
    st.markdown(
        f"""
<div class="hero">
  <h2 style="margin:0">Undervalued Cashflow Screener</h2>
  <p style="margin:.3rem 0 0 0">{country_label} | Last refresh: {updated_at}</p>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("추천 종목 수", rec_count)
    c2.metric("표본 종목 수", len(df))
    c3.metric("중앙 멀티플", "-" if np.isnan(med) else f"{med:.2f}")


def render_filters(df: pd.DataFrame) -> dict:
    st.sidebar.subheader("필터")
    sectors = sorted([x for x in df.get("sector", pd.Series(dtype=str)).dropna().unique().tolist() if x])
    selected_sectors = st.sidebar.multiselect("섹터", sectors)
    mult_min, mult_max = st.sidebar.slider("멀티플 범위", 0.0, 30.0, (0.0, 30.0), 0.1)
    vip_only = st.sidebar.checkbox("VIP 조건만", value=False)
    keyword = st.sidebar.text_input("검색(티커/종목명)", value="")
    return {
        "sectors": selected_sectors,
        "multiple_min": mult_min,
        "multiple_max": mult_max,
        "vip_only": vip_only,
        "keyword": keyword,
    }


def render_recommend_treemap(df: pd.DataFrame) -> None:
    rec = df[df["is_recommended"]].copy()
    st.subheader("추천 종목 맵")
    if rec.empty:
        st.info("조건을 만족하는 추천 종목이 없습니다.")
        return

    rec["log_cap"] = np.log(rec["market_cap"].clip(lower=1.0))
    rec["label"] = rec["name"].fillna(rec["symbol"]) + " (" + rec["symbol"] + ")"
    fig = px.treemap(
        rec,
        path=["label"],
        values="log_cap",
        color="multiple",
        color_continuous_scale="Tealgrn",
        hover_data={
            "market_cap": ":.3s",
            "multiple": ":.2f",
            "sales_trend": True,
            "vip_pass": True,
            "log_cap": False,
        },
    )
    fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=560)
    st.plotly_chart(fig, use_container_width=True)


def render_table(df: pd.DataFrame) -> None:
    st.subheader("상세 테이블")
    show = df.copy()
    show["추천"] = np.where(show["is_recommended"], "Y", "N")
    show["VIP"] = np.where(show["vip_pass"], "Y", "N")
    cols = [
        "추천",
        "VIP",
        "symbol",
        "name",
        "sector",
        "market_cap",
        "multiple",
        "sales_trend",
        "rejection_reason",
        "currency",
    ]
    st.dataframe(show[cols], use_container_width=True, hide_index=True)
    st.download_button(
        "CSV 다운로드",
        data=show.to_csv(index=False).encode("utf-8-sig"),
        file_name="valuation_screen.csv",
        mime="text/csv",
    )
