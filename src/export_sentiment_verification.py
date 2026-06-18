import sqlite3
import pandas as pd
from pathlib import Path
from src.db_schema import DEFAULT_DB_PATH

def export_verification_csv():
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    
    # 1. Get the latest sentiment scores for all companies
    df_sentiment = pd.read_sql_query("""
        SELECT 
            s.ticker, 
            t.company_name,
            s.general_sentiment_score,
            s.ai_demand_sentiment,
            s.data_center_sentiment,
            s.hbm_sentiment,
            s.foundry_capacity_sentiment,
            s.semiconductor_capex_sentiment,
            s.china_export_risk_sentiment,
            s.inventory_sentiment,
            s.gross_margin_sentiment,
            s.pricing_pressure_sentiment,
            s.automotive_demand_sentiment,
            s.consumer_demand_sentiment,
            s.industrial_demand_sentiment,
            s.optical_networking_sentiment,
            s.memory_pricing_sentiment,
            s.analyst_sentiment,
            s.management_tone_sentiment,
            s.risk_sentiment
        FROM sentiment_daily s
        JOIN ticker_master t ON s.ticker = t.ticker
    """, conn)
    
    # 2. For each company, fetch the 10 news headlines and URLs that we used
    headlines_list = []
    urls_list = []
    
    for ticker in df_sentiment['ticker']:
        df_news = pd.read_sql_query("""
            SELECT headline, url 
            FROM news_events 
            WHERE ticker=? AND is_company_specific=1
            ORDER BY published_at DESC LIMIT 10
        """, conn, params=(ticker,))
        
        headlines = " | ".join(df_news['headline'].dropna().tolist())
        urls = " | ".join(df_news['url'].dropna().tolist())
        
        headlines_list.append(headlines)
        urls_list.append(urls)
        
    df_sentiment['news_headlines'] = headlines_list
    df_sentiment['news_urls'] = urls_list
    
    # 3. Save to CSV
    output_path = Path("data/output/sentiment_verification_export.csv")
    df_sentiment.to_csv(output_path, index=False)
    print(f"Exported {len(df_sentiment)} companies to {output_path}")
    
    conn.close()

if __name__ == "__main__":
    export_verification_csv()
