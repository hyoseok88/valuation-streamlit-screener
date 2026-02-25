from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_hero(country_label: str, updated_at: str, df: pd.DataFrame) -> None:
    rec_count = int(df["is_recommended"].sum()) if not df.empty else 0
    strong_count = int(df.get("strong_recommend", pd.Series(dtype=bool)).sum()) if not df.empty else 0
    med = float(df["multiple"].dropna().median()) if not df.empty and df["multiple"].notna().any() else float("nan")
    coverage = float(df["multiple"].notna().mean() * 100.0) if not df.empty else 0.0
    st.markdown(
        f"""
<div class="hero">
  <h2 style="margin:0">Undervalued Cashflow Screener</h2>
  <p style="margin:.3rem 0 0 0">{country_label} | Last refresh: {updated_at}</p>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("추천 종목 수", rec_count)
    c2.metric("강력추천 수", strong_count)
    c3.metric("표본 종목 수", len(df))
    c4.metric("중앙 멀티플", "-" if np.isnan(med) else f"{med:.2f}")
    c5.metric("지표 산출률", f"{coverage:.1f}%")

    if not df.empty and df["multiple"].isna().any():
        missing_reasons = (
            df[df["multiple"].isna()]["rejection_reason"]
            .fillna("데이터 부족")
            .replace("", "데이터 부족")
            .value_counts()
            .head(3)
        )
        reason_text = ", ".join([f"{idx} {cnt}건" for idx, cnt in missing_reasons.items()])
        if reason_text:
            st.caption(f"지표 미산출 상위 원인: {reason_text}")


def render_filters(df: pd.DataFrame) -> dict:
    st.sidebar.subheader("필터")
    sectors = sorted([x for x in df.get("sector", pd.Series(dtype=str)).dropna().unique().tolist() if x])
    selected_sectors = st.sidebar.multiselect("섹터", sectors)
    mult_min, mult_max = st.sidebar.slider("멀티플 범위", 0.0, 30.0, (0.0, 30.0), 0.1)
    vip_only = st.sidebar.checkbox("VIP 조건만", value=False)
    keyword = st.sidebar.text_input("목록 필터 검색(티커/종목명)", value="")
    st.sidebar.subheader("개별 티커 조회")
    ticker_lookup = st.sidebar.text_input("티커 입력", value="", placeholder="예: 005930 / AAPL / 7203")
    return {
        "sectors": selected_sectors,
        "multiple_min": mult_min,
        "multiple_max": mult_max,
        "vip_only": vip_only,
        "keyword": keyword,
        "ticker_lookup": ticker_lookup,
    }


def render_single_ticker_result(result: dict | None) -> None:
    if result is None:
        return

    st.subheader("개별 티커 조회 결과")
    name = result.get("name") or result.get("symbol") or "-"
    symbol = result.get("symbol") or "-"
    multiple = result.get("multiple")
    vip_pass = bool(result.get("vip_pass"))
    is_recommended = bool(result.get("is_recommended"))
    strong_recommend = bool(result.get("strong_recommend"))
    reason = result.get("rejection_reason") or "-"
    trend = result.get("sales_trend") or "판정불가"
    market_cap = result.get("market_cap")
    currency = result.get("currency") or "N/A"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("종목", f"{name} ({symbol})")
    c2.metric("멀티플", "-" if multiple is None else f"{float(multiple):.2f}")
    c3.metric("VIP 추천 여부", "Y" if vip_pass else "N")
    c4.metric("저평가 추천 여부", "Y" if is_recommended else "N")
    c5.metric("강력추천 여부", "Y" if strong_recommend else "N")

    cap_text = "-" if market_cap is None else f"{float(market_cap):,.0f} {currency}"
    st.caption(f"시가총액: {cap_text} | 매출추세: {trend} | 미추천/미산출 사유: {reason}")


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


def render_strong_recommendations(df: pd.DataFrame) -> None:
    st.subheader("강력추천 (우상향 + 멀티플<=10)")
    if df.empty or "strong_recommend" not in df.columns:
        st.info("강력추천 종목이 없습니다.")
        return

    strong = df[df["strong_recommend"]].copy()
    if strong.empty:
        st.info("강력추천 종목이 없습니다.")
        return

    strong["강력추천"] = "Y"
    cols = [
        "강력추천",
        "symbol",
        "name",
        "sector",
        "market_cap",
        "multiple",
        "sales_trend",
        "currency",
    ]
    strong = strong.sort_values(by=["multiple", "market_cap"], ascending=[True, False])
    st.dataframe(strong[cols], use_container_width=True, hide_index=True)


def render_table(df: pd.DataFrame) -> None:
    st.subheader("상세 테이블")
    show = df.copy()
    show["추천"] = np.where(show["is_recommended"], "Y", "N")
    show["강력추천"] = np.where(show.get("strong_recommend", False), "Y", "N")
    show["VIP"] = np.where(show["vip_pass"], "Y", "N")
    cols = [
        "강력추천",
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


def _fmt_price(value: float | None, currency: str) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.2f} {currency}"


def _fmt_number(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.0f}"


def _fmt_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100.0:.2f}%"


def _fmt_pct_direct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2f}%"


def render_target_price_result(result: dict | None) -> None:
    if result is None:
        st.info("사이드바에서 종목 코드/명을 입력하면 목표가를 계산합니다.")
        return

    symbol = result.get("symbol") or "-"
    name = result.get("name") or symbol
    currency = result.get("currency") or "N/A"
    float_rate_pct = result.get("float_rate_pct")
    multiplier = result.get("multiplier")
    weekly = result.get("weekly_frame")
    breakout_ts = result.get("breakout_week_end")

    st.subheader("검색종목 목표가 산출")
    float_rate_label = "-" if float_rate_pct is None or pd.isna(float_rate_pct) else f"{float(float_rate_pct):.1f}%"
    multiplier_label = "-" if multiplier is None or pd.isna(multiplier) else f"{float(multiplier):.1f}"
    st.caption(
        f"{name} ({symbol}) | 유동비율 입력값: {float_rate_label} | 목표가 배수: {multiplier_label}"
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("현재가", _fmt_price(result.get("current_price"), currency))
    c2.metric("52주 이평선", _fmt_price(result.get("ma52_price"), currency))
    c3.metric("최근 돌파 시점", result.get("breakout_week") or "-")
    c4.metric("에너지 비율", _fmt_pct(result.get("energy_ratio")))
    c5.metric("목표가", _fmt_price(result.get("target_price"), currency))
    c6.metric("상승 여력", _fmt_pct_direct(result.get("upside_pct")))

    cap_text = _fmt_number(result.get("market_cap"))
    float_cap_text = _fmt_number(result.get("floating_cap"))
    breakout_val_text = _fmt_number(result.get("breakout_trading_value"))
    st.caption(
        "총 시가총액: "
        f"{cap_text} {currency} | 유통 시가총액: {float_cap_text} {currency} | "
        f"돌파 주 거래대금: {breakout_val_text} {currency}"
    )

    if result.get("error"):
        st.warning(result["error"])

    if not isinstance(weekly, pd.DataFrame) or weekly.empty:
        return

    chart_df = weekly.tail(180).copy()
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=chart_df.index,
            open=chart_df["Open"],
            high=chart_df["High"],
            low=chart_df["Low"],
            close=chart_df["Close"],
            name="Weekly OHLC",
            increasing_line_color="#0d9488",
            decreasing_line_color="#dc2626",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=chart_df.index,
            y=chart_df["MA52"],
            mode="lines",
            name="MA52",
            line=dict(color="#2563eb", width=2),
        )
    )

    target_price = result.get("target_price")
    if target_price is not None and not pd.isna(target_price):
        fig.add_trace(
            go.Scatter(
                x=chart_df.index,
                y=[float(target_price)] * len(chart_df),
                mode="lines",
                name="Target Price",
                line=dict(color="#f59e0b", width=2, dash="dash"),
            )
        )

    if breakout_ts is not None and breakout_ts in chart_df.index:
        fig.add_trace(
            go.Scatter(
                x=[breakout_ts],
                y=[chart_df.loc[breakout_ts, "Close"]],
                mode="markers",
                name="최근 돌파 주",
                marker=dict(color="#7c3aed", size=9, symbol="diamond"),
            )
        )

    fig.update_layout(
        height=620,
        margin=dict(t=16, b=12, l=12, r=12),
        xaxis_title="Week",
        yaxis_title=f"Price ({currency})",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True)
