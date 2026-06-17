"""SQLite schema for the semiconductor market data foundation.

14 tables covering: identity, daily market state, market context, earnings,
sentiment, news, fundamentals, valuation, relationships, calendar, ownership,
and model-ready features.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "semiconductor_data.db"


def create_database(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create (or open) the database and ensure all tables exist."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_all_tables(conn)
    return conn


def _create_all_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # ──────────────────────────────────────────────
    # TABLE 1: ticker_master
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ticker_master (
        ticker                          TEXT PRIMARY KEY,
        company_name                    TEXT,
        exchange                        TEXT,
        country                         TEXT,
        currency                        TEXT,
        primary_listing                 TEXT,
        is_adr                          INTEGER DEFAULT 0,
        cik                             TEXT,
        isin                            TEXT,
        figi                            TEXT,
        sector                          TEXT,
        industry                        TEXT,
        gics_sector                     TEXT,
        gics_industry                   TEXT,
        semiconductor_category          TEXT,
        business_role                   TEXT,
        company_description             TEXT,
        main_products                   TEXT,
        main_end_markets                TEXT,
        main_themes                     TEXT,
        ai_exposure_score               REAL DEFAULT 0.0,
        data_center_exposure_score      REAL DEFAULT 0.0,
        consumer_exposure_score         REAL DEFAULT 0.0,
        automotive_exposure_score       REAL DEFAULT 0.0,
        industrial_exposure_score       REAL DEFAULT 0.0,
        china_exposure_score            REAL DEFAULT 0.0,
        memory_cycle_exposure_score     REAL DEFAULT 0.0,
        foundry_exposure_score          REAL DEFAULT 0.0,
        equipment_cycle_exposure_score  REAL DEFAULT 0.0,
        optical_networking_exposure_score REAL DEFAULT 0.0,
        ai_overview                     TEXT,
        market_cap                      REAL,
        shares_outstanding              REAL,
        float_shares                    REAL,
        average_daily_volume_20d        REAL,
        average_dollar_volume_20d       REAL,
        liquidity_score                 REAL,
        risk_bucket                     TEXT,
        last_updated                    TEXT
    )
    """)

    # ──────────────────────────────────────────────
    # TABLE 2: ticker_daily_market_state
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ticker_daily_market_state (
        date                                TEXT NOT NULL,
        ticker                              TEXT NOT NULL,
        open                                REAL,
        high                                REAL,
        low                                 REAL,
        close                               REAL,
        adjusted_close                      REAL,
        volume                              REAL,
        dollar_volume                       REAL,
        return_1d                           REAL,
        return_3d                           REAL,
        return_5d                           REAL,
        return_10d                          REAL,
        return_20d                          REAL,
        return_60d                          REAL,
        gap_percent                         REAL,
        intraday_range_percent              REAL,
        close_position_in_daily_range       REAL,
        volume_ratio_20d                    REAL,
        volume_ratio_60d                    REAL,
        volatility_20d                      REAL,
        volatility_60d                      REAL,
        atr_14d                             REAL,
        rolling_beta_vs_spy_60d             REAL,
        rolling_beta_vs_qqq_60d             REAL,
        rolling_beta_vs_smh_60d             REAL,
        rolling_correlation_vs_spy_60d      REAL,
        rolling_correlation_vs_qqq_60d      REAL,
        rolling_correlation_vs_smh_60d      REAL,
        rolling_correlation_vs_nvda_60d     REAL,
        rolling_correlation_vs_soxx_60d     REAL,
        relative_strength_vs_spy_5d         REAL,
        relative_strength_vs_qqq_5d         REAL,
        relative_strength_vs_smh_5d         REAL,
        relative_strength_vs_spy_20d        REAL,
        relative_strength_vs_qqq_20d        REAL,
        relative_strength_vs_smh_20d        REAL,
        abnormal_return_vs_spy_1d           REAL,
        abnormal_return_vs_qqq_1d           REAL,
        abnormal_return_vs_smh_1d           REAL,
        abnormal_return_vs_soxx_1d          REAL,
        abnormal_return_vs_theme_basket_1d  REAL,
        abnormal_return_vs_smh_3d           REAL,
        abnormal_return_vs_smh_5d           REAL,
        market_regime                       TEXT,
        semiconductor_regime                TEXT,
        theme_regime                        TEXT,
        data_quality_flag                   TEXT,
        PRIMARY KEY (date, ticker)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tdms_ticker ON ticker_daily_market_state(ticker)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tdms_date ON ticker_daily_market_state(date)")

    # ──────────────────────────────────────────────
    # TABLE 3: market_context_daily
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_context_daily (
        date                        TEXT PRIMARY KEY,
        spy_return_1d               REAL,
        qqq_return_1d               REAL,
        iwm_return_1d               REAL,
        smh_return_1d               REAL,
        soxx_return_1d              REAL,
        vix_level                   REAL,
        vix_change_1d               REAL,
        usd_index_return_1d         REAL,
        ten_year_yield_change_1d    REAL,
        nasdaq_market_breadth       REAL,
        semiconductor_breadth       REAL,
        percent_semis_green         REAL,
        percent_semis_above_20dma   REAL,
        market_regime               TEXT,
        semiconductor_regime        TEXT,
        risk_on_risk_off_score      REAL,
        ai_theme_strength_score     REAL
    )
    """)

    # ──────────────────────────────────────────────
    # TABLE 4: earnings_events
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS earnings_events (
        event_id                                TEXT PRIMARY KEY,
        ticker                                  TEXT NOT NULL,
        event_date                              TEXT NOT NULL,
        report_time                             TEXT,
        fiscal_year                             TEXT,
        fiscal_quarter                          TEXT,
        eps_estimate                            REAL,
        eps_actual                              REAL,
        eps_surprise                            REAL,
        eps_surprise_percent                    REAL,
        revenue_estimate                        REAL,
        revenue_actual                          REAL,
        revenue_surprise                        REAL,
        revenue_surprise_percent                REAL,
        gross_margin_actual                     REAL,
        gross_margin_estimate                   REAL,
        gross_margin_surprise                   REAL,
        guidance_direction                      TEXT,
        guidance_strength_score                 REAL,
        guidance_revenue_next_q                 REAL,
        guidance_eps_next_q                     REAL,
        guidance_margin_commentary              TEXT,
        pre_earnings_return_1d                  REAL,
        pre_earnings_return_5d                  REAL,
        pre_earnings_return_20d                 REAL,
        post_earnings_return_1d                 REAL,
        post_earnings_return_3d                 REAL,
        post_earnings_return_5d                 REAL,
        post_earnings_return_10d                REAL,
        post_earnings_abnormal_return_vs_smh_1d REAL,
        post_earnings_abnormal_return_vs_smh_3d REAL,
        post_earnings_abnormal_return_vs_smh_5d REAL,
        post_earnings_abnormal_return_vs_qqq_1d REAL,
        volume_ratio_on_earnings_day            REAL,
        earnings_move_direction                 TEXT,
        earnings_event_type                     TEXT,
        earnings_quality_score                  REAL,
        market_reaction_score                   REAL,
        event_summary                           TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ee_ticker ON earnings_events(ticker)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ee_date ON earnings_events(event_date)")

    # ──────────────────────────────────────────────
    # TABLE 5: ticker_earnings_profile
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ticker_earnings_profile (
        ticker                                          TEXT PRIMARY KEY,
        earnings_event_count                            INTEGER,
        average_post_earnings_return_1d                  REAL,
        average_post_earnings_return_3d                  REAL,
        average_post_earnings_return_5d                  REAL,
        median_post_earnings_return_1d                   REAL,
        median_post_earnings_return_3d                   REAL,
        median_post_earnings_return_5d                   REAL,
        average_post_earnings_abnormal_return_vs_smh_1d  REAL,
        average_post_earnings_abnormal_return_vs_smh_3d  REAL,
        average_post_earnings_abnormal_return_vs_smh_5d  REAL,
        positive_reaction_rate                           REAL,
        negative_reaction_rate                           REAL,
        beat_positive_reaction_rate                      REAL,
        miss_negative_reaction_rate                      REAL,
        average_upside_after_positive_surprise           REAL,
        average_downside_after_negative_surprise         REAL,
        max_positive_earnings_move                       REAL,
        max_negative_earnings_move                       REAL,
        earnings_volatility_score                        REAL,
        sample_size_confidence                           REAL,
        last_updated                                     TEXT
    )
    """)

    # ──────────────────────────────────────────────
    # TABLE 6: sentiment_daily
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sentiment_daily (
        date                            TEXT NOT NULL,
        ticker                          TEXT NOT NULL,
        general_sentiment_score         REAL,
        general_sentiment_label         TEXT,
        sentiment_change_1d             REAL,
        sentiment_change_3d             REAL,
        sentiment_change_7d             REAL,
        news_count                      INTEGER,
        high_quality_news_count         INTEGER,
        social_attention_score          REAL,
        source_confidence_score         REAL,
        ai_demand_sentiment             REAL,
        data_center_sentiment           REAL,
        hbm_sentiment                   REAL,
        foundry_capacity_sentiment      REAL,
        semiconductor_capex_sentiment   REAL,
        china_export_risk_sentiment     REAL,
        inventory_sentiment             REAL,
        gross_margin_sentiment          REAL,
        pricing_pressure_sentiment      REAL,
        automotive_demand_sentiment     REAL,
        consumer_demand_sentiment       REAL,
        industrial_demand_sentiment     REAL,
        optical_networking_sentiment    REAL,
        memory_pricing_sentiment        REAL,
        analyst_sentiment               REAL,
        management_tone_sentiment       REAL,
        risk_sentiment                  REAL,
        sentiment_summary               TEXT,
        PRIMARY KEY (date, ticker)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sd_ticker ON sentiment_daily(ticker)")

    # ──────────────────────────────────────────────
    # TABLE 7: news_events
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS news_events (
        news_id                 TEXT PRIMARY KEY,
        published_at            TEXT,
        ticker                  TEXT,
        headline                TEXT,
        source                  TEXT,
        url                     TEXT,
        news_category           TEXT,
        news_importance_score   REAL,
        sentiment_score         REAL,
        topic_tags              TEXT,
        mentioned_companies     TEXT,
        related_tickers         TEXT,
        is_company_specific     INTEGER,
        is_sector_wide          INTEGER,
        is_macro_related        INTEGER,
        summary                 TEXT,
        possible_market_impact  TEXT,
        data_quality_flag       TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ne_ticker ON news_events(ticker)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ne_date ON news_events(published_at)")

    # ──────────────────────────────────────────────
    # TABLE 8: fundamentals_quarterly
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fundamentals_quarterly (
        ticker                  TEXT NOT NULL,
        fiscal_year             TEXT,
        fiscal_quarter          TEXT,
        period_end_date         TEXT NOT NULL,
        revenue                 REAL,
        revenue_growth_yoy      REAL,
        revenue_growth_qoq      REAL,
        gross_profit            REAL,
        gross_margin            REAL,
        operating_income        REAL,
        operating_margin        REAL,
        net_income              REAL,
        net_margin              REAL,
        eps_diluted             REAL,
        free_cash_flow          REAL,
        free_cash_flow_margin   REAL,
        cash_and_equivalents    REAL,
        total_debt              REAL,
        net_debt                REAL,
        debt_to_equity          REAL,
        inventory               REAL,
        inventory_growth_yoy    REAL,
        inventory_days          REAL,
        capex                   REAL,
        capex_growth_yoy        REAL,
        r_and_d_expense         REAL,
        r_and_d_as_percent_revenue REAL,
        accounts_receivable     REAL,
        days_sales_outstanding  REAL,
        backlog                 REAL,
        book_to_bill            REAL,
        fundamental_quality_score REAL,
        PRIMARY KEY (ticker, period_end_date)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fq_ticker ON fundamentals_quarterly(ticker)")

    # ──────────────────────────────────────────────
    # TABLE 9: valuation_snapshot
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS valuation_snapshot (
        date                        TEXT NOT NULL,
        ticker                      TEXT NOT NULL,
        market_cap                  REAL,
        enterprise_value            REAL,
        price_to_sales_ttm          REAL,
        price_to_sales_forward      REAL,
        price_to_earnings_ttm       REAL,
        price_to_earnings_forward   REAL,
        ev_to_sales                 REAL,
        ev_to_ebitda                REAL,
        price_to_book               REAL,
        free_cash_flow_yield        REAL,
        revenue_growth_forward      REAL,
        eps_growth_forward          REAL,
        valuation_percentile_1y     REAL,
        valuation_percentile_3y     REAL,
        valuation_risk_score        REAL,
        PRIMARY KEY (date, ticker)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vs_ticker ON valuation_snapshot(ticker)")

    # ──────────────────────────────────────────────
    # TABLE 10: company_relationships
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS company_relationships (
        relationship_id             TEXT PRIMARY KEY,
        source_ticker               TEXT NOT NULL,
        target_ticker               TEXT NOT NULL,
        relationship_type           TEXT,
        relationship_category       TEXT,
        expected_effect_direction    TEXT,
        relationship_strength_score REAL,
        confidence_score            REAL,
        evidence_source             TEXT,
        evidence_url                TEXT,
        evidence_text               TEXT,
        is_verified                 INTEGER DEFAULT 0,
        source_filing_date          TEXT,
        expected_lag_min_days        INTEGER,
        expected_lag_max_days        INTEGER,
        historical_lag_observed     REAL,
        relationship_start_date     TEXT,
        relationship_end_date       TEXT,
        notes                       TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cr_source ON company_relationships(source_ticker)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cr_target ON company_relationships(target_ticker)")

    # ──────────────────────────────────────────────
    # TABLE 11: ticker_relationship_profile
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ticker_relationship_profile (
        ticker                                  TEXT PRIMARY KEY,
        number_of_upstream_relationships         INTEGER DEFAULT 0,
        number_of_downstream_relationships       INTEGER DEFAULT 0,
        number_of_customer_relationships         INTEGER DEFAULT 0,
        number_of_supplier_relationships         INTEGER DEFAULT 0,
        number_of_competitor_relationships        INTEGER DEFAULT 0,
        number_of_theme_relationships            INTEGER DEFAULT 0,
        average_relationship_strength            REAL,
        average_relationship_confidence          REAL,
        top_source_tickers_that_affect_this_ticker TEXT,
        top_target_tickers_this_ticker_affects    TEXT,
        main_relationship_categories             TEXT,
        relationship_dependency_score            REAL,
        theme_dependency_score                   REAL,
        supplier_customer_dependency_score       REAL
    )
    """)

    # ──────────────────────────────────────────────
    # TABLE 12: calendar_events
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS calendar_events (
        event_id                TEXT PRIMARY KEY,
        ticker                  TEXT,
        event_date              TEXT NOT NULL,
        event_type              TEXT,
        event_time              TEXT,
        event_importance_score  REAL,
        description             TEXT,
        related_tickers         TEXT,
        expected_topics         TEXT,
        is_before_market        INTEGER,
        is_after_market         INTEGER
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ce_ticker ON calendar_events(ticker)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ce_date ON calendar_events(event_date)")

    # ──────────────────────────────────────────────
    # TABLE 13: ownership_flow_optional
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ownership_flow_optional (
        date                            TEXT NOT NULL,
        ticker                          TEXT NOT NULL,
        short_interest_percent_float    REAL,
        days_to_cover                   REAL,
        institutional_ownership_percent REAL,
        insider_ownership_percent       REAL,
        recent_insider_buying           REAL,
        recent_insider_selling          REAL,
        etf_ownership_percent           REAL,
        largest_etf_holders             TEXT,
        options_volume                  REAL,
        put_call_ratio                  REAL,
        implied_volatility              REAL,
        iv_percentile_1y                REAL,
        flow_risk_score                 REAL,
        PRIMARY KEY (date, ticker)
    )
    """)
    # ──────────────────────────────────────────────
    # TABLE 15: sector_sentiment_daily
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sector_sentiment_daily (
        date                            TEXT NOT NULL,
        sector                          TEXT NOT NULL,
        general_sentiment_score         REAL,
        ai_demand_sentiment             REAL,
        data_center_sentiment           REAL,
        hbm_sentiment                   REAL,
        foundry_capacity_sentiment      REAL,
        semiconductor_capex_sentiment   REAL,
        china_export_risk_sentiment     REAL,
        inventory_sentiment             REAL,
        gross_margin_sentiment          REAL,
        pricing_pressure_sentiment      REAL,
        automotive_demand_sentiment     REAL,
        consumer_demand_sentiment       REAL,
        industrial_demand_sentiment     REAL,
        optical_networking_sentiment    REAL,
        memory_pricing_sentiment        REAL,
        analyst_sentiment               REAL,
        management_tone_sentiment       REAL,
        risk_sentiment                  REAL,
        sector_overview                 TEXT,
        PRIMARY KEY (date, sector)
    )
    """)

    # ──────────────────────────────────────────────
    # TABLE 16: market_sentiment_daily
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_sentiment_daily (
        date                            TEXT PRIMARY KEY,
        general_sentiment_score         REAL,
        ai_demand_sentiment             REAL,
        data_center_sentiment           REAL,
        hbm_sentiment                   REAL,
        foundry_capacity_sentiment      REAL,
        semiconductor_capex_sentiment   REAL,
        china_export_risk_sentiment     REAL,
        inventory_sentiment             REAL,
        gross_margin_sentiment          REAL,
        pricing_pressure_sentiment      REAL,
        automotive_demand_sentiment     REAL,
        consumer_demand_sentiment       REAL,
        industrial_demand_sentiment     REAL,
        optical_networking_sentiment    REAL,
        memory_pricing_sentiment        REAL,
        analyst_sentiment               REAL,
        management_tone_sentiment       REAL,
        risk_sentiment                  REAL,
        macro_market_overview           TEXT
    )
    """)

    # ──────────────────────────────────────────────
    # TABLE 14: model_ready_features_later
    # ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_ready_features_later (
        date                            TEXT NOT NULL,
        ticker                          TEXT NOT NULL,
        raw_return_1d                   REAL,
        abnormal_return_vs_smh_1d       REAL,
        relative_strength_vs_smh_5d     REAL,
        volume_ratio_20d                REAL,
        volatility_20d                  REAL,
        sentiment_score                 REAL,
        sentiment_change_3d             REAL,
        ai_demand_sentiment             REAL,
        data_center_sentiment           REAL,
        china_risk_sentiment            REAL,
        earnings_event_nearby           INTEGER,
        days_until_earnings             INTEGER,
        days_since_earnings             INTEGER,
        latest_eps_surprise_percent     REAL,
        latest_revenue_surprise_percent REAL,
        guidance_strength_score         REAL,
        fundamental_quality_score       REAL,
        valuation_risk_score            REAL,
        relationship_dependency_score   REAL,
        market_regime                   TEXT,
        semiconductor_regime            TEXT,
        theme_regime                    TEXT,
        PRIMARY KEY (date, ticker)
    )
    """)

    conn.commit()


def get_table_stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Return row counts for all tables."""
    cur = conn.cursor()
    tables = [
        "ticker_master", "ticker_daily_market_state", "market_context_daily",
        "earnings_events", "ticker_earnings_profile", "sentiment_daily",
        "news_events", "fundamentals_quarterly", "valuation_snapshot",
        "company_relationships", "ticker_relationship_profile",
        "calendar_events", "ownership_flow_optional", "model_ready_features_later",
    ]
    stats = {}
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cur.fetchone()[0]
        except sqlite3.OperationalError:
            stats[table] = -1
    return stats


if __name__ == "__main__":
    conn = create_database()
    print(f"Database created at: {DEFAULT_DB_PATH}")
    stats = get_table_stats(conn)
    for table, count in stats.items():
        print(f"  {table}: {count} rows")
    conn.close()
