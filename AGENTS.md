# AGENTS.md

Guidance for Codex agents working on this repository.

## Project Purpose

This project builds a semiconductor and AI infrastructure market dashboard. It combines prices, company news, AI/Gemini sentiment, macro/sector sentiment, thematic exposures, relationship graph data, and historical earnings/news experiments.

The main user-facing artifact is:

- `data/output/relationship_map_v4.html`

The app is usually served locally with:

```bash
python -m http.server 8000
```

Then open:

```text
http://127.0.0.1:8000/data/output/relationship_map_v4.html
```

## Setup

Use Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The shell script `run_daily_update.sh` may contain a machine-specific `cd` path. On a new machine, update that path or run the module commands manually from the repo root.

## API Keys

Do not commit API keys or secrets.

Expected environment variables:

- `GEMINI_API_KEY` for Gemini sentiment generation.
- `APCA_API_KEY_ID` for Alpaca historical news tests.
- `APCA_API_SECRET_KEY` for Alpaca historical news tests.
- `BENZINGA_API_KEY` for direct Benzinga news tests.

Use a local `.env` file if needed, but keep it untracked.

## Daily Pipeline

Normal daily run order:

```bash
python -m src.pipeline_daily_market
python -m src.pipeline_secondary
python -m src.pipeline_ai_sentiment
python -m src.pipeline_macro_sentiment
python -m src.generate_enhanced_map
```

The full sentiment run has usually taken about 1-2 minutes for the macro/sector Gemini pass, plus seconds for map generation. Timing depends on API/network latency.

If Gemini is unavailable, `src.pipeline_macro_sentiment` has a deterministic fallback, but the preferred output is Gemini-grounded using actual news evidence.

## Important Sentiment Rules

Company sentiment must only use company-specific news. Do not allow sector, competitor, or generic semiconductor headlines to drive a company ticker score.

Example failure to avoid:

- An Intel 18A-P headline should not be shown as the latest NVIDIA driver.

The relevant filtering logic is in:

- `src/news_relevance.py`
- `src/pipeline_secondary.py`
- `src/pipeline_ai_sentiment.py`
- `src/pipeline_ai_overview.py`
- `src/export_sentiment_verification.py`
- `src/generate_enhanced_map.py`

For company panels and company AI overview, prefer rows where:

- `is_company_specific = 1`

Sector and macro sentiment should use layered evidence:

- Company-specific news for constituents in that sector.
- Broad sector/macro news relevant to that sector.
- Market-wide macro evidence for the general semiconductor market.

Macro/sector summaries should be grounded in actual fetched text and existing company sentiment scores. They should not be generic Gemini hallucinations.

## Macro Sentiment

Main file:

- `src/pipeline_macro_sentiment.py`

Current intended behavior:

- Build sector sentiment from real underlying news and company scores.
- Send full article text where available.
- Preserve energy as its own sector sentiment.
- Exclude energy from the overall semiconductor market average.
- Use modest language for weak numeric scores.

Score language:

- `< 0.15`: weak/neutral
- `0.15-0.29`: modest
- `0.30-0.49`: moderate
- `0.50+`: strong

The user cares that macro sentiment contains readable summaries and that broad categories such as energy, macro, and semiconductor are separated from specific supply-chain groups like foundry/equipment/device.

## Thematic Exposures

Thematic exposure logic is in:

- `src/thematic_exposures.py`
- `src/update_thematic_exposures.py`
- `src/pipeline_ticker_master.py`
- `src/generate_enhanced_map.py`

The map recomputes exposures at generation time and includes an `Energy/Grid` axis. Keep these exposures grounded in business descriptions, sector/subsector, keywords, and relevant relationship context. Avoid making every semiconductor ticker look identical.

## Historical News Experiments

Alpaca historical news:

- `src/try_alpaca_news.py`

Example:

```bash
python -m src.try_alpaca_news --symbol MU --start 2023-06-01 --end 2023-07-01 --max-pages 10 --out-csv data/output/alpaca_news_MU_2023-06-01_2023-07-01.csv
```

Fetch article bodies:

- `src/fetch_article_bodies.py`

Article quality filtering:

- `src/article_quality.py`

Direct Benzinga tests:

- `src/try_benzinga_news.py`

The one-month MU Alpaca test produced `data/output/alpaca_news_MU_2023-06-01_2023-07-01_with_quality.csv`. The quality classifier marks usable articles versus noisy rows such as headline-only, generic multi-ticker, boilerplate-only, or not-company-relevant.

## Article Quality Policy

For sentiment, prefer articles marked usable by `src/article_quality.py`:

- `full_text_relevant`
- `short_text_relevant`

Be careful with:

- `headline_only`
- `generic_multi_ticker`
- `boilerplate_only`
- `not_company_relevant`

The user prefers filtering useless/noisy articles instead of letting them contaminate sentiment.

## Generated Outputs

Important outputs live in:

- `data/output/relationship_map_v4.html`
- `data/output/sentiment_verification_export.csv`
- `data/output/alpaca_news_*`
- `data/output/benzinga_news_*`

Some CSV outputs are generated artifacts and may change from local runs. Do not commit unrelated output churn unless the user asks for it.

Known local output files that were intentionally not committed in the latest handoff because they were unrelated earnings churn:

- `data/output/best_earnings_stocks_ranked.csv`
- `data/output/earnings_reactions_raw.csv`
- `data/output/earnings_reactions_summary_by_stock.csv`
- `data/output/failed_tickers.csv`

## Git Notes

Before pushing:

```bash
git status --short
git diff --check
```

If the remote has newer commits, fetch/rebase rather than force-pushing:

```bash
git fetch origin main
git rebase origin/main
git push origin main
```

Never force-push without explicit user approval.

## User Preferences From Prior Work

- Keep the app runnable locally.
- Do not run expensive/API-heavy sentiment steps unless the user asks.
- Do not paste or commit secrets.
- Prefer real, grounded evidence over generic AI wording.
- For ticker sentiment, strict ticker relevance matters more than broad market vibes.
- For macro sentiment, include the news/evidence memory so the user can inspect why Gemini created the score.
- The dashboard should make macro sentiment visible without blocking the graph UI.
