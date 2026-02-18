# Streamlit Cloud Deploy Guide

## 1) Create App
1. Open https://share.streamlit.io/
2. Click `New app`
3. Repository: `hyoseok88/valuation-streamlit-screener`
4. Branch: `main`
5. Main file path: `app.py`
6. Deploy

## 2) First Boot Checks
1. App opens without crash
2. Sidebar country switch works
3. Treemap and table render
4. `데이터 새로고침` button works

## 3) If build fails
1. Verify Python runtime: `3.11` (from `runtime.txt`)
2. Check logs for missing package
3. Reboot app from Streamlit settings

## 4) Operations
- Data is refreshed daily by GitHub Actions and committed into `data_cache/`
- Streamlit app reads cached files first for fast load
