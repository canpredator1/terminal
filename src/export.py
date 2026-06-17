"""CSV export helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATE_COLUMNS = {
    "earnings_date",
    "price_7d_before_date",
    "earnings_nearest_trading_date",
    "price_7d_after_date",
}

PRICE_COLUMNS = {
    "price_7d_before_adj_close",
    "earnings_nearest_adj_close",
    "price_7d_after_adj_close",
}

PERCENTAGE_COLUMNS = {
    "eps_surprise_pct",
    "change_7d_before_to_earnings_pct",
    "change_earnings_to_7d_after_pct",
    "change_7d_before_to_7d_after_pct",
    "average_change_7d_before_to_7d_after_pct",
    "median_change_7d_before_to_7d_after_pct",
    "average_change_earnings_to_7d_after_pct",
    "median_change_earnings_to_7d_after_pct",
    "positive_7d_window_rate",
    "best_7d_window_return_pct",
    "worst_7d_window_return_pct",
    "average_eps_surprise_pct",
    "median_eps_surprise_pct",
    "ranking_score",
}

EPS_VALUE_COLUMNS = {
    "eps_estimate",
    "reported_eps",
    "eps_surprise",
    "average_reported_eps",
    "average_eps_estimate",
}


def _prepare_for_export(df: pd.DataFrame) -> pd.DataFrame:
    export_df = df.copy()

    for column in DATE_COLUMNS.intersection(export_df.columns):
        export_df[column] = pd.to_datetime(export_df[column], errors="coerce").dt.strftime(
            "%Y-%m-%d"
        )

    for column in PRICE_COLUMNS.intersection(export_df.columns):
        export_df[column] = pd.to_numeric(export_df[column], errors="coerce").round(4)

    for column in PERCENTAGE_COLUMNS.intersection(export_df.columns):
        export_df[column] = pd.to_numeric(export_df[column], errors="coerce").round(2)

    for column in EPS_VALUE_COLUMNS.intersection(export_df.columns):
        export_df[column] = pd.to_numeric(export_df[column], errors="coerce").round(4)

    return export_df


def _save_dataframe(df: pd.DataFrame, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_for_export(df).to_csv(output_path, index=False)


def save_raw_csv(df: pd.DataFrame, output_path: str | Path) -> None:
    _save_dataframe(df, output_path)


def save_summary_csv(df: pd.DataFrame, output_path: str | Path) -> None:
    _save_dataframe(df, output_path)


def save_ranked_csv(df: pd.DataFrame, output_path: str | Path) -> None:
    _save_dataframe(df, output_path)


def save_failed_tickers_csv(df: pd.DataFrame, output_path: str | Path) -> None:
    _save_dataframe(df, output_path)
