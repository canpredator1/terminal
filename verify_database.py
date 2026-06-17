import sqlite3
import pandas as pd
from pathlib import Path
from src.db_schema import DEFAULT_DB_PATH, get_table_stats

def verify_database():
    print(f"\n{'='*50}\nVerifying Database Quality\n{'='*50}")
    
    if not Path(DEFAULT_DB_PATH).exists():
        print(f"Error: Database {DEFAULT_DB_PATH} not found.")
        return
        
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    
    # Check row counts
    stats = get_table_stats(conn)
    print("Table Row Counts:")
    for t, c in stats.items():
        print(f"  {t}: {c}")
        
    print("\nData Quality Checks:")
    
    # 1. Missing tickers in ticker_master?
    c1 = pd.read_sql_query('SELECT COUNT(*) FROM ticker_master', conn).iloc[0,0]
    print(f"  Tickers populated: {c1}/112")
    
    # 2. Check earnings events linkage
    c2 = pd.read_sql_query('''
        SELECT COUNT(DISTINCT ticker) 
        FROM earnings_events 
        WHERE ticker NOT IN (SELECT ticker FROM ticker_master)
    ''', conn).iloc[0,0]
    print(f"  Earnings with missing master ticker: {c2}")
    
    # 3. Check relationships linkage
    c3 = pd.read_sql_query('''
        SELECT COUNT(DISTINCT source_ticker) 
        FROM company_relationships 
        WHERE source_ticker NOT IN (SELECT ticker FROM ticker_master)
    ''', conn).iloc[0,0]
    print(f"  Relationship sources with missing master ticker: {c3}")
    
    # 4. Check for Nulls in Daily Market
    if stats.get('ticker_daily_market_state', 0) > 0:
        c4 = pd.read_sql_query('''
            SELECT COUNT(*) FROM ticker_daily_market_state 
            WHERE return_1d IS NULL OR volume IS NULL
        ''', conn).iloc[0,0]
        print(f"  Daily market state records with null return/volume: {c4}")
        
    # 5. Check if sentiment got generated
    if stats.get('sentiment_daily', 0) > 0:
        c5 = pd.read_sql_query('''
            SELECT AVG(general_sentiment_score) as avg_sent,
                   SUM(news_count) as total_news
            FROM sentiment_daily
        ''', conn)
        print(f"  Average sentiment score: {c5.iloc[0]['avg_sent']:.3f}, Total news: {c5.iloc[0]['total_news']}")
        
    conn.close()
    
if __name__ == '__main__':
    verify_database()
