import sqlite3

import pandas as pd

from src.db_schema import DEFAULT_DB_PATH
from src.thematic_exposures import DB_EXPOSURE_COLUMNS, score_ticker_exposures


def update_thematic_exposures() -> None:
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    latest_sent_date = cur.execute("SELECT MAX(date) FROM sentiment_daily").fetchone()[0]
    sentiment = {}
    if latest_sent_date:
        df_sent = pd.read_sql_query(
            "SELECT * FROM sentiment_daily WHERE date = ?",
            conn,
            params=(latest_sent_date,),
        )
        sentiment = {row["ticker"]: row.dropna().to_dict() for _, row in df_sent.iterrows()}

    rows = cur.execute(
        """
        SELECT ticker, company_name, semiconductor_category, company_description,
               main_products, main_end_markets, main_themes
        FROM ticker_master
        """
    ).fetchall()

    updates = []
    for row in rows:
        scores = score_ticker_exposures(
            row["ticker"],
            row["semiconductor_category"],
            company_name=row["company_name"],
            description=row["company_description"],
            products=row["main_products"],
            markets=row["main_end_markets"],
            themes=row["main_themes"],
            sentiment=sentiment.get(row["ticker"], {}),
        )
        updates.append(
            (
                *(scores[key] for key in DB_EXPOSURE_COLUMNS),
                row["ticker"],
            )
        )

    columns = ", ".join(f"{column}=?" for column in DB_EXPOSURE_COLUMNS.values())
    cur.executemany(
        f"UPDATE ticker_master SET {columns} WHERE ticker=?",
        updates,
    )
    conn.commit()
    conn.close()
    print(f"Updated thematic exposures for {len(updates)} tickers.")


if __name__ == "__main__":
    update_thematic_exposures()
