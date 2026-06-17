import sqlite3
import pandas as pd
from pathlib import Path

from src.db_schema import DEFAULT_DB_PATH

def populate_earnings():
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cur = conn.cursor()
    
    raw_path = Path('data/output/earnings_reactions_raw.csv')
    sum_path = Path('data/output/earnings_reactions_summary_by_stock.csv')
    
    if not raw_path.exists() or not sum_path.exists():
        print("Earnings CSVs not found.")
        return
        
    print("Populating earnings events...")
    raw_df = pd.read_csv(raw_path)
    
    events_rows = []
    for _, row in raw_df.iterrows():
        ticker = row['ticker']
        date = row['earnings_date']
        event_id = f"{ticker}_{date}"
        
        eps_surp_pct = row.get('eps_surprise_pct', 0)
        if pd.isna(eps_surp_pct): eps_surp_pct = 0
            
        post_ret_1d = row.get('change_earnings_to_7d_after_pct', 0) # proxy for 1d if not available
        if pd.isna(post_ret_1d): post_ret_1d = 0
            
        # Classify event
        etype = 'neutral'
        if eps_surp_pct > 0 and post_ret_1d > 0:
            etype = 'beat_and_rally'
        elif eps_surp_pct > 0 and post_ret_1d < 0:
            etype = 'beat_and_sell'
        elif eps_surp_pct < 0 and post_ret_1d < 0:
            etype = 'miss_and_sell'
        elif eps_surp_pct < 0 and post_ret_1d > 0:
            etype = 'miss_and_rally'
            
        quality = abs(eps_surp_pct) * 0.3 + abs(post_ret_1d) * 0.7
        
        events_rows.append((
            event_id, ticker, date, None, None, None,
            row.get('eps_estimate'), row.get('reported_eps'), row.get('eps_surprise'), eps_surp_pct,
            None, None, None, None, None, None, None, # revenue & margins
            None, None, None, None, None, # guidance
            row.get('change_7d_before_to_earnings_pct'), None, None, # pre
            post_ret_1d, None, row.get('change_earnings_to_7d_after_pct'), None, # post
            None, None, None, None, None, # abnormals
            'up' if post_ret_1d > 0 else 'down',
            etype, quality, post_ret_1d,
            row.get('data_quality_notes')
        ))
        
    cur.executemany('''
        INSERT OR REPLACE INTO earnings_events (
            event_id, ticker, event_date, report_time, fiscal_year, fiscal_quarter,
            eps_estimate, eps_actual, eps_surprise, eps_surprise_percent,
            revenue_estimate, revenue_actual, revenue_surprise, revenue_surprise_percent,
            gross_margin_actual, gross_margin_estimate, gross_margin_surprise,
            guidance_direction, guidance_strength_score, guidance_revenue_next_q,
            guidance_eps_next_q, guidance_margin_commentary,
            pre_earnings_return_1d, pre_earnings_return_5d, pre_earnings_return_20d,
            post_earnings_return_1d, post_earnings_return_3d, post_earnings_return_5d, post_earnings_return_10d,
            post_earnings_abnormal_return_vs_smh_1d, post_earnings_abnormal_return_vs_smh_3d,
            post_earnings_abnormal_return_vs_smh_5d, post_earnings_abnormal_return_vs_qqq_1d,
            volume_ratio_on_earnings_day, earnings_move_direction, earnings_event_type,
            earnings_quality_score, market_reaction_score, event_summary
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', events_rows)
    
    print("Populating earnings profiles...")
    sum_df = pd.read_csv(sum_path)
    prof_rows = []
    
    for _, row in sum_df.iterrows():
        count = row.get('number_of_earnings_events', 0)
        prof_rows.append((
            row['ticker'], count,
            row.get('average_change_earnings_to_7d_after_pct'), None, row.get('average_change_7d_before_to_7d_after_pct'),
            row.get('median_change_earnings_to_7d_after_pct'), None, row.get('median_change_7d_before_to_7d_after_pct'),
            None, None, None,
            row.get('positive_7d_window_rate'), 100 - row.get('positive_7d_window_rate', 100) if not pd.isna(row.get('positive_7d_window_rate')) else None,
            None, None, None, None,
            row.get('best_7d_window_return_pct'), row.get('worst_7d_window_return_pct'),
            None, min(1.0, count / 12), pd.Timestamp.now().isoformat()
        ))
        
    cur.executemany('''
        INSERT OR REPLACE INTO ticker_earnings_profile (
            ticker, earnings_event_count,
            average_post_earnings_return_1d, average_post_earnings_return_3d, average_post_earnings_return_5d,
            median_post_earnings_return_1d, median_post_earnings_return_3d, median_post_earnings_return_5d,
            average_post_earnings_abnormal_return_vs_smh_1d, average_post_earnings_abnormal_return_vs_smh_3d,
            average_post_earnings_abnormal_return_vs_smh_5d, positive_reaction_rate, negative_reaction_rate,
            beat_positive_reaction_rate, miss_negative_reaction_rate, average_upside_after_positive_surprise,
            average_downside_after_negative_surprise, max_positive_earnings_move, max_negative_earnings_move,
            earnings_volatility_score, sample_size_confidence, last_updated
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', prof_rows)
    
    conn.commit()
    conn.close()
    print("Done populating earnings.")

if __name__ == '__main__':
    populate_earnings()
