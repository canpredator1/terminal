"""Earnings data helpers backed by yfinance."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import yfinance as yf
from dateutil.relativedelta import relativedelta

EARNINGS_COLUMNS = [
    "earnings_date",
    "eps_estimate",
    "reported_eps",
    "yfinance_surprise_pct",
]


def _empty_earnings_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=EARNINGS_COLUMNS)


def _normalize_column_name(column_name: object) -> str:
    normalized = str(column_name).strip().lower()
    normalized = normalized.replace("%", " pct ")
    normalized = normalized.replace("(", " ").replace(")", " ")
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def _coerce_numeric_column(df: pd.DataFrame, column_name: str) -> pd.Series:
    if column_name not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[column_name], errors="coerce")


def get_earnings_for_ticker(ticker: str, lookback_years: int = 3) -> pd.DataFrame:
    """Return a normalized earnings DataFrame for one ticker.

    The yfinance earnings calendar can expose slightly different column names
    across versions, so this function normalizes them into a stable schema.
    """

    try:
        earnings_df = yf.Ticker(ticker).get_earnings_dates(limit=20)
    except ImportError as exc:
        raise RuntimeError(
            "yfinance earnings scraping requires lxml. Install dependencies from requirements.txt."
        ) from exc

    if earnings_df is None or earnings_df.empty:
        return _empty_earnings_frame()

    working_df = earnings_df.copy()

    if isinstance(working_df.index, pd.DatetimeIndex):
        working_df = working_df.reset_index()

    working_df = working_df.rename(
        columns={column: _normalize_column_name(column) for column in working_df.columns}
    )

    if "earnings_date" not in working_df.columns:
        for fallback_column in ("date", "index"):
            if fallback_column in working_df.columns:
                working_df = working_df.rename(columns={fallback_column: "earnings_date"})
                break

    if "earnings_date" not in working_df.columns:
        raise ValueError(f"Could not find an earnings date column for {ticker}.")

    earnings_dates = pd.to_datetime(working_df["earnings_date"], errors="coerce")
    if getattr(earnings_dates.dt, "tz", None) is not None:
        earnings_dates = earnings_dates.dt.tz_localize(None)

    cleaned_df = pd.DataFrame(
        {
            "earnings_date": earnings_dates.dt.normalize(),
            "eps_estimate": _coerce_numeric_column(working_df, "eps_estimate"),
            "reported_eps": _coerce_numeric_column(working_df, "reported_eps"),
            "yfinance_surprise_pct": _coerce_numeric_column(working_df, "surprise_pct"),
        }
    )

    today = pd.Timestamp.today().normalize()
    cutoff_date = (today - relativedelta(years=lookback_years)).normalize()

    cleaned_df = cleaned_df.loc[
        cleaned_df["earnings_date"].notna()
        & (cleaned_df["earnings_date"] >= cutoff_date)
        & (cleaned_df["earnings_date"] <= today)
    ]

    cleaned_df = (
        cleaned_df.drop_duplicates(subset=["earnings_date"], keep="first")
        .sort_values("earnings_date", ascending=False)
        .reset_index(drop=True)
    )

    return cleaned_df[EARNINGS_COLUMNS]
