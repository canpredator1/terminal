"""Build CSV datasets for stock reactions around earnings reports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf
from dateutil.relativedelta import relativedelta
from tqdm import tqdm

from src.calculations import (
    RANKED_OUTPUT_COLUMNS,
    RAW_OUTPUT_COLUMNS,
    SUMMARY_OUTPUT_COLUMNS,
    calculate_best_earnings_stocks_ranked,
    calculate_earnings_reaction_rows,
    calculate_summary_by_stock,
)
from src.earnings import get_earnings_for_ticker
from src.export import (
    save_failed_tickers_csv,
    save_ranked_csv,
    save_raw_csv,
    save_summary_csv,
)
from src.prices import get_price_history
from src.tickers import TICKERS

LOOKBACK_YEARS = 3


def get_company_name(ticker: str) -> str:
    """Return the best available display name for a ticker."""

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return ticker

    return info.get("shortName") or info.get("longName") or ticker


def print_summary(
    raw_df: pd.DataFrame,
    ranked_df: pd.DataFrame,
    failed_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    successful_tickers = len(TICKERS) - len(failed_df)
    print("\nRun complete.")
    print(f"Tickers processed: {len(TICKERS)}")
    print(f"Successful tickers: {successful_tickers}")
    print(f"Failed tickers: {len(failed_df)}")
    print(f"Total earnings events collected: {len(raw_df)}")

    print("\nTop 5 ranked stocks by eps_beat_reaction_score:")
    if ranked_df.empty:
        print("No ranked results were available.")
    else:
        preview_columns = ["rank", "ticker", "company_name", "eps_beat_reaction_score"]
        print(ranked_df[preview_columns].head(5).to_string(index=False))

    print("\nOutput files:")
    print(f"- {output_dir / 'earnings_reactions_raw.csv'}")
    print(f"- {output_dir / 'earnings_reactions_summary_by_stock.csv'}")
    print(f"- {output_dir / 'best_earnings_stocks_ranked.csv'}")
    print(f"- {output_dir / 'failed_tickers.csv'}")


def main() -> None:
    project_root = Path(__file__).resolve().parent
    output_dir = project_root / "data" / "output"

    today = pd.Timestamp.today().normalize()
    lookback_start = (today - relativedelta(years=LOOKBACK_YEARS)).normalize()
    price_start = lookback_start - pd.Timedelta(days=20)
    price_end = today + pd.Timedelta(days=20)

    raw_frames: list[pd.DataFrame] = []
    failed_tickers: list[dict[str, str]] = []

    for ticker in tqdm(TICKERS, desc="Processing tickers"):
        try:
            company_name = get_company_name(ticker)
            earnings_df = get_earnings_for_ticker(ticker, lookback_years=LOOKBACK_YEARS)

            if not earnings_df.empty:
                price_df = get_price_history(ticker, price_start, price_end)
                ticker_raw_df = calculate_earnings_reaction_rows(
                    ticker=ticker,
                    company_name=company_name,
                    earnings_df=earnings_df,
                    price_df=price_df,
                )
                if not ticker_raw_df.empty:
                    raw_frames.append(ticker_raw_df)
        except Exception as exc:
            failed_tickers.append({"ticker": ticker, "error_message": str(exc)})

    raw_df = (
        pd.concat(raw_frames, ignore_index=True)
        if raw_frames
        else pd.DataFrame(columns=RAW_OUTPUT_COLUMNS)
    )
    raw_df = (
        raw_df.drop_duplicates(subset=["ticker", "earnings_date"], keep="first")
        .sort_values(["ticker", "earnings_date"], ascending=[True, False])
        .reset_index(drop=True)
    )

    summary_df = calculate_summary_by_stock(raw_df)
    ranked_df = calculate_best_earnings_stocks_ranked(summary_df)
    failed_df = pd.DataFrame(failed_tickers, columns=["ticker", "error_message"])

    save_raw_csv(raw_df, output_dir / "earnings_reactions_raw.csv")
    save_summary_csv(summary_df, output_dir / "earnings_reactions_summary_by_stock.csv")
    save_ranked_csv(ranked_df, output_dir / "best_earnings_stocks_ranked.csv")
    save_failed_tickers_csv(failed_df, output_dir / "failed_tickers.csv")

    print_summary(raw_df, ranked_df, failed_df, output_dir)


if __name__ == "__main__":
    main()
