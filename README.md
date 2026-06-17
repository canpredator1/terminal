# Semiconductor Earnings Reaction Dataset

This project builds CSV datasets that analyze how major AI and semiconductor stocks move around earnings reports using only `yfinance` for earnings dates and historical price data.

The source code uses the requested libraries plus `lxml` in `requirements.txt` because current `yfinance` releases require it at runtime for `Ticker.get_earnings_dates(limit=20)`.

## Python version

Use Python 3.11 or newer.

## Ticker universe

Version 1 uses this manual ticker list:

- `NVDA`
- `AMD`
- `AVGO`
- `TSM`
- `ASML`
- `ARM`
- `MU`
- `MRVL`
- `QCOM`
- `INTC`
- `AMAT`
- `LRCX`
- `KLAC`
- `TXN`
- `ADI`
- `ON`
- `MPWR`
- `MCHP`
- `NXPI`
- `TER`
- `COHR`
- `SMCI`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

From the project root:

```bash
python3 main.py
```

The script will:

1. Pull earnings dates with `Ticker.get_earnings_dates(limit=20)`.
2. Filter to historical earnings events from the last 3 years.
3. Download daily price history with adjusted close values.
4. Find the nearest trading day for:
   - 7 calendar days before earnings
   - the earnings date itself
   - 7 calendar days after earnings
5. Build event-level, summary, ranking, and failed-ticker CSV files.

## Event window logic

Each earnings event uses a 14-calendar-day window:

- `earnings_date - 7 calendar days`
- `earnings_date`
- `earnings_date + 7 calendar days`

If an exact date is not a trading day, the script uses the nearest available trading day in the downloaded historical price DataFrame. If two trading days are equally close, it chooses the earlier date to keep the behavior deterministic.

## Output files

All output files are written to `data/output/`.

### 1. `earnings_reactions_raw.csv`

One row per ticker per earnings event.

Columns:

- `ticker`: stock symbol
- `company_name`: company name from `yfinance` info when available
- `earnings_date`: normalized earnings date
- `eps_estimate`: earnings estimate from `yfinance`
- `reported_eps`: reported EPS from `yfinance`
- `eps_surprise`: `reported_eps - eps_estimate`
- `eps_surprise_pct`: `((reported_eps - eps_estimate) / abs(eps_estimate)) * 100`
- `price_7d_before_date`: nearest trading day to `earnings_date - 7 days`
- `price_7d_before_adj_close`: adjusted close on that date
- `earnings_nearest_trading_date`: nearest trading day to the earnings date
- `earnings_nearest_adj_close`: adjusted close on that date
- `price_7d_after_date`: nearest trading day to `earnings_date + 7 days`
- `price_7d_after_adj_close`: adjusted close on that date
- `change_7d_before_to_earnings_pct`: `((earnings_nearest_adj_close - price_7d_before_adj_close) / price_7d_before_adj_close) * 100`
- `change_earnings_to_7d_after_pct`: `((price_7d_after_adj_close - earnings_nearest_adj_close) / earnings_nearest_adj_close) * 100`
- `change_7d_before_to_7d_after_pct`: `((price_7d_after_adj_close - price_7d_before_adj_close) / price_7d_before_adj_close) * 100`
- `data_quality_notes`: notes for missing EPS data, missing price data, or incomplete calculations

Sorting:

- Sorted by `ticker` ascending
- Then `earnings_date` descending

### 2. `earnings_reactions_summary_by_stock.csv`

One row per ticker with summary statistics.

Columns:

- `ticker`
- `company_name`
- `number_of_earnings_events`
- `average_change_7d_before_to_7d_after_pct`
- `median_change_7d_before_to_7d_after_pct`
- `average_change_earnings_to_7d_after_pct`
- `median_change_earnings_to_7d_after_pct`
- `positive_7d_window_count`
- `negative_7d_window_count`
- `positive_7d_window_rate`
- `best_7d_window_return_pct`
- `worst_7d_window_return_pct`
- `average_eps_surprise_pct`
- `median_eps_surprise_pct`
- `average_reported_eps`
- `average_eps_estimate`

Definitions:

- `positive_7d_window_count`: count of events where `change_7d_before_to_7d_after_pct > 0`
- `negative_7d_window_count`: count of events where `change_7d_before_to_7d_after_pct < 0`
- `positive_7d_window_rate`: `positive_7d_window_count / number_of_earnings_events`

### 3. `best_earnings_stocks_ranked.csv`

Stocks ranked from best to worst using a simple historical earnings-window score.

Columns:

- `rank`
- `ticker`
- `company_name`
- `number_of_earnings_events`
- `positive_7d_window_rate`
- `average_change_7d_before_to_7d_after_pct`
- `median_change_7d_before_to_7d_after_pct`
- `average_change_earnings_to_7d_after_pct`
- `average_eps_surprise_pct`
- `best_7d_window_return_pct`
- `worst_7d_window_return_pct`
- `ranking_score`

Ranking formula:

```text
ranking_score =
positive_7d_window_rate * 50
+ average_change_7d_before_to_7d_after_pct
+ average_eps_surprise_pct * 0.1
```

Missing `average_eps_surprise_pct` values are treated as `0` in the score.

### 4. `failed_tickers.csv`

Contains any ticker that failed during processing.

Columns:

- `ticker`
- `error_message`

## Data quality behavior

- The script continues even if one ticker fails.
- Duplicate earnings dates for the same ticker are removed.
- Missing earnings data returns an empty result for that ticker instead of crashing.
- If required price points are missing, percentage changes are left blank and the reason is written to `data_quality_notes`.
- Percentage fields are rounded to 2 decimals.
- Price fields are rounded to 4 decimals.

## Project structure

```text
semiconductor_earnings_reaction/
├── main.py
├── requirements.txt
├── README.md
├── data/
│   └── output/
└── src/
    ├── tickers.py
    ├── earnings.py
    ├── prices.py
    ├── calculations.py
    └── export.py
```
