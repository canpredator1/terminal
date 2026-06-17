import sqlite3
import pandas as pd
import json

def export_amd_experiment():
    # 1. The parsed JSON results from our experiment
    amd_results = {
      "general_sentiment_score": 0.4,
      "general_sentiment_label": "positive",
      "ai_demand_sentiment": 0.9,
      "data_center_sentiment": 0.9,
      "hbm_sentiment": 0.0,
      "foundry_capacity_sentiment": 0.2,
      "semiconductor_capex_sentiment": 0.6,
      "china_export_risk_sentiment": -0.5,
      "inventory_sentiment": 0.0,
      "gross_margin_sentiment": -0.2,
      "pricing_pressure_sentiment": 0.6,
      "automotive_demand_sentiment": 0.0,
      "consumer_demand_sentiment": -0.7,
      "industrial_demand_sentiment": 0.0,
      "optical_networking_sentiment": 0.0,
      "memory_pricing_sentiment": 0.5,
      "analyst_sentiment": 0.8,
      "management_tone_sentiment": 0.6,
      "risk_sentiment": 0.8,
      "sentiment_summary": "AMD exhibits strong positive sentiment driven by its significant advancements and market share gains in AI and data center segments, supported by bullish analyst ratings, though tempered by concerns over high valuation, a projected decline in its gaming division, and potential regulatory risks."
    }
    
    # 2. Get the links we used
    conn = sqlite3.connect("data/semiconductor_data.db")
    df_news = pd.read_sql_query(f"""
        SELECT url 
        FROM news_events 
        WHERE ticker='AMD' 
        ORDER BY published_at DESC LIMIT 10
    """, conn)
    conn.close()
    
    urls = " | ".join(df_news['url'].dropna().tolist())
    
    # 3. Create a DataFrame and export
    amd_results["ticker"] = "AMD"
    amd_results["experiment_type"] = "Full Text Article Analysis"
    amd_results["news_urls_analyzed"] = urls
    
    df = pd.DataFrame([amd_results])
    
    # Reorder columns to make it nice
    cols = ['ticker', 'experiment_type', 'news_urls_analyzed'] + [c for c in df.columns if c not in ['ticker', 'experiment_type', 'news_urls_analyzed']]
    df = df[cols]
    
    output_path = "data/output/amd_full_text_experiment.csv"
    df.to_csv(output_path, index=False)
    print(f"Exported to {output_path}")

if __name__ == "__main__":
    export_amd_experiment()
