"""Calculation helpers for earnings-window reaction analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd

RAW_OUTPUT_COLUMNS = [
    "ticker",
    "company_name",
    "earnings_date",
    "eps_estimate",
    "reported_eps",
    "eps_surprise",
    "eps_surprise_pct",
    "price_7d_before_date",
    "price_7d_before_adj_close",
    "earnings_nearest_trading_date",
    "earnings_nearest_adj_close",
    "price_7d_after_date",
    "price_7d_after_adj_close",
    "change_7d_before_to_earnings_pct",
    "change_earnings_to_7d_after_pct",
    "change_7d_before_to_7d_after_pct",
    "data_quality_notes",
]

SUMMARY_OUTPUT_COLUMNS = [
    "ticker",
    "company_name",
    "number_of_earnings_events",
    "average_change_7d_before_to_7d_after_pct",
    "median_change_7d_before_to_7d_after_pct",
    "average_change_earnings_to_7d_after_pct",
    "median_change_earnings_to_7d_after_pct",
    "positive_7d_window_count",
    "negative_7d_window_count",
    "positive_7d_window_rate",
    "best_7d_window_return_pct",
    "worst_7d_window_return_pct",
    "average_eps_surprise_pct",
    "median_eps_surprise_pct",
    "average_reported_eps",
    "average_eps_estimate",
    "eps_beat_rate",
    "average_return_on_eps_beat_pct",
    "median_return_on_eps_beat_pct",
]

RANKED_OUTPUT_COLUMNS = [
    "rank",
    "ticker",
    "company_name",
    "number_of_earnings_events",
    "positive_7d_window_rate",
    "average_change_7d_before_to_7d_after_pct",
    "median_change_7d_before_to_7d_after_pct",
    "average_change_earnings_to_7d_after_pct",
    "average_eps_surprise_pct",
    "best_7d_window_return_pct",
    "worst_7d_window_return_pct",
    "ranking_score",
    "eps_beat_rate",
    "average_return_on_eps_beat_pct",
    "eps_beat_reaction_score",
]


def nearest_trading_day(
    price_df: pd.DataFrame, target_date: pd.Timestamp | str
) -> tuple[pd.Timestamp | pd.NaT, float]:
    """Return the nearest trading day and adjusted close for a target calendar date.

    When two trading days are equally close, the earlier trading day wins so
    the output is deterministic and avoids looking further ahead than needed.
    """

    if price_df.empty or "adj_close" not in price_df.columns:
        return pd.NaT, np.nan

    target_ts = pd.Timestamp(target_date).normalize()

    if target_ts in price_df.index:
        return target_ts, float(price_df.loc[target_ts, "adj_close"])

    insert_position = price_df.index.searchsorted(target_ts)
    candidates: list[pd.Timestamp] = []

    if insert_position > 0:
        candidates.append(price_df.index[insert_position - 1])
    if insert_position < len(price_df.index):
        candidates.append(price_df.index[insert_position])

    if not candidates:
        return pd.NaT, np.nan

    nearest_date = min(
        candidates,
        key=lambda candidate: (abs((candidate - target_ts).days), candidate),
    )
    return nearest_date, float(price_df.loc[nearest_date, "adj_close"])


def _empty_raw_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=RAW_OUTPUT_COLUMNS)


def _safe_pct_change(start_value: float, end_value: float) -> float:
    if pd.isna(start_value) or pd.isna(end_value) or start_value == 0:
        return np.nan
    return ((end_value - start_value) / start_value) * 100


def calculate_earnings_reaction_rows(
    ticker: str,
    company_name: str,
    earnings_df: pd.DataFrame,
    price_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build one raw output row per earnings event."""

    if earnings_df.empty:
        return _empty_raw_frame()

    rows: list[dict[str, object]] = []

    for record in earnings_df.to_dict(orient="records"):
        earnings_date = pd.Timestamp(record["earnings_date"]).normalize()
        eps_estimate = record.get("eps_estimate")
        reported_eps = record.get("reported_eps")

        before_date, before_price = nearest_trading_day(
            price_df, earnings_date - pd.Timedelta(days=7)
        )
        earnings_trade_date, earnings_price = nearest_trading_day(price_df, earnings_date)
        after_date, after_price = nearest_trading_day(
            price_df, earnings_date + pd.Timedelta(days=7)
        )

        notes: list[str] = []
        if pd.isna(eps_estimate):
            notes.append("missing eps estimate")
        if pd.isna(reported_eps):
            notes.append("missing reported eps")

        eps_surprise = np.nan
        if pd.notna(reported_eps) and pd.notna(eps_estimate):
            eps_surprise = reported_eps - eps_estimate

        eps_surprise_pct = np.nan
        if pd.notna(reported_eps) and pd.notna(eps_estimate):
            if eps_estimate == 0:
                notes.append("eps estimate is zero; surprise pct unavailable")
            else:
                eps_surprise_pct = ((reported_eps - eps_estimate) / abs(eps_estimate)) * 100

        missing_price_points = []
        if pd.isna(before_price):
            missing_price_points.append("7d before price")
        if pd.isna(earnings_price):
            missing_price_points.append("earnings date price")
        if pd.isna(after_price):
            missing_price_points.append("7d after price")

        if missing_price_points:
            notes.append(f"missing price data: {', '.join(missing_price_points)}")
            notes.append("insufficient price data for percentage-change calculations")

        rows.append(
            {
                "ticker": ticker,
                "company_name": company_name,
                "earnings_date": earnings_date,
                "eps_estimate": eps_estimate,
                "reported_eps": reported_eps,
                "eps_surprise": eps_surprise,
                "eps_surprise_pct": eps_surprise_pct,
                "price_7d_before_date": before_date,
                "price_7d_before_adj_close": before_price,
                "earnings_nearest_trading_date": earnings_trade_date,
                "earnings_nearest_adj_close": earnings_price,
                "price_7d_after_date": after_date,
                "price_7d_after_adj_close": after_price,
                "change_7d_before_to_earnings_pct": _safe_pct_change(
                    before_price, earnings_price
                ),
                "change_earnings_to_7d_after_pct": _safe_pct_change(
                    earnings_price, after_price
                ),
                "change_7d_before_to_7d_after_pct": _safe_pct_change(
                    before_price, after_price
                ),
                "data_quality_notes": "; ".join(dict.fromkeys(notes)),
            }
        )

    output_df = pd.DataFrame(rows, columns=RAW_OUTPUT_COLUMNS)
    output_df = output_df.drop_duplicates(subset=["ticker", "earnings_date"], keep="first")
    return output_df


def calculate_summary_by_stock(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the raw event-level dataset into one summary row per ticker."""

    if raw_df.empty:
        return pd.DataFrame(columns=SUMMARY_OUTPUT_COLUMNS)

    summary_rows: list[dict[str, object]] = []

    grouped = raw_df.groupby(["ticker", "company_name"], dropna=False, sort=True)
    for (ticker, company_name), group_df in grouped:
        window_returns = group_df["change_7d_before_to_7d_after_pct"]
        post_earnings_returns = group_df["change_earnings_to_7d_after_pct"]
        eps_surprise_pct = group_df["eps_surprise_pct"]

        positive_count = int((window_returns > 0).sum())
        negative_count = int((window_returns < 0).sum())
        event_count = int(len(group_df))
        
        beat_events = group_df[group_df["eps_surprise_pct"] > 0]
        eps_beat_count = len(beat_events)
        beat_returns = beat_events["change_7d_before_to_7d_after_pct"]

        summary_rows.append(
            {
                "ticker": ticker,
                "company_name": company_name,
                "number_of_earnings_events": event_count,
                "average_change_7d_before_to_7d_after_pct": window_returns.mean(),
                "median_change_7d_before_to_7d_after_pct": window_returns.median(),
                "average_change_earnings_to_7d_after_pct": post_earnings_returns.mean(),
                "median_change_earnings_to_7d_after_pct": post_earnings_returns.median(),
                "positive_7d_window_count": positive_count,
                "negative_7d_window_count": negative_count,
                "positive_7d_window_rate": positive_count / event_count if event_count else np.nan,
                "best_7d_window_return_pct": window_returns.max(),
                "worst_7d_window_return_pct": window_returns.min(),
                "average_eps_surprise_pct": eps_surprise_pct.mean(),
                "median_eps_surprise_pct": eps_surprise_pct.median(),
                "average_reported_eps": group_df["reported_eps"].mean(),
                "average_eps_estimate": group_df["eps_estimate"].mean(),
                "eps_beat_rate": eps_beat_count / event_count if event_count else np.nan,
                "average_return_on_eps_beat_pct": beat_returns.mean() if eps_beat_count else np.nan,
                "median_return_on_eps_beat_pct": beat_returns.median() if eps_beat_count else np.nan,
            }
        )

    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_OUTPUT_COLUMNS)
    summary_df = summary_df.sort_values(["ticker", "company_name"]).reset_index(drop=True)
    return summary_df


def calculate_best_earnings_stocks_ranked(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Rank stocks based on a simple historical earnings-window score."""

    if summary_df.empty:
        return pd.DataFrame(columns=RANKED_OUTPUT_COLUMNS)

    ranked_df = summary_df.copy()
    ranked_df["ranking_score"] = (
        ranked_df["positive_7d_window_rate"].fillna(0) * 50
        + ranked_df["average_change_7d_before_to_7d_after_pct"].fillna(0)
        + ranked_df["average_eps_surprise_pct"].fillna(0) * 0.1
    )
    
    ranked_df["eps_beat_reaction_score"] = (
        ranked_df["eps_beat_rate"].fillna(0) * 50
        + ranked_df["average_return_on_eps_beat_pct"].fillna(0)
    )

    ranked_df = ranked_df.sort_values(
        ["eps_beat_reaction_score", "ticker"], ascending=[False, True]
    ).reset_index(drop=True)
    ranked_df.insert(0, "rank", range(1, len(ranked_df) + 1))

    return ranked_df[RANKED_OUTPUT_COLUMNS]
