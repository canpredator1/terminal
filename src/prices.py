"""Historical price download helpers backed by yfinance."""

from __future__ import annotations

from typing import Iterable

import pandas as pd
import yfinance as yf


def _flatten_columns(columns: Iterable[object]) -> list[str]:
    flattened = []
    for column in columns:
        if isinstance(column, tuple):
            flattened.append(" ".join(str(part) for part in column if str(part)).strip())
        else:
            flattened.append(str(column))
    return flattened


def get_price_history(
    ticker: str, start_date: pd.Timestamp | str, end_date: pd.Timestamp | str
) -> pd.DataFrame:
    """Download daily price history and return a clean adjusted-close DataFrame."""

    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize() + pd.Timedelta(days=1)

    price_df = yf.download(
        ticker,
        start=start_ts.strftime("%Y-%m-%d"),
        end=end_ts.strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=False,
        progress=False,
        actions=False,
        threads=False,
    )

    if price_df is None or price_df.empty:
        return pd.DataFrame(columns=["adj_close"])

    working_df = price_df.copy()
    if isinstance(working_df.columns, pd.MultiIndex):
        working_df.columns = _flatten_columns(working_df.columns.to_flat_index())

    adj_close_candidates = [column for column in working_df.columns if "Adj Close" in column]
    if adj_close_candidates:
        working_df = working_df[[adj_close_candidates[0]]].rename(
            columns={adj_close_candidates[0]: "adj_close"}
        )
    elif "Close" in working_df.columns:
        # Fallback for yfinance builds that surface an already-adjusted close column.
        working_df = working_df[["Close"]].rename(columns={"Close": "adj_close"})
    else:
        return pd.DataFrame(columns=["adj_close"])

    working_df.index = pd.to_datetime(working_df.index, errors="coerce")
    working_df = working_df.loc[working_df.index.notna()].copy()

    if getattr(working_df.index, "tz", None) is not None:
        working_df.index = working_df.index.tz_localize(None)

    working_df.index = working_df.index.normalize()
    working_df["adj_close"] = pd.to_numeric(working_df["adj_close"], errors="coerce")
    working_df = working_df.dropna(subset=["adj_close"])
    working_df = working_df.loc[~working_df.index.duplicated(keep="last")]
    working_df = working_df.sort_index()

    return working_df
