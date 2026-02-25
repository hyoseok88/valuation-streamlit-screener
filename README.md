# Undervalued Valuation Screener

Streamlit app for country-based undervalued stock screening:
- Universe: KR Top 200, US Top 500, JP Top 200, EU Top 200
- Metric: Market Cap / Sum of latest 4Q Operating Cash Flow
- Recommendation: multiple <= 14
- Extra: 5Y revenue trend, VIP 224/112 moving-average condition

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Daily Refresh

```bash
python -m src.jobs.daily_refresh
```

## Target Price Default Tuning

```bash
python -m src.jobs.optimize_target_price_defaults --country KR_TOP200
```

Latest KR tuning artifact:
- `data_cache/target_price_grid_search_kr.json`
- `data_cache/target_price_grid_search_kr.csv`
