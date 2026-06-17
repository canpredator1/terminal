import os
import sqlite3
import pandas as pd
import datetime
import time
from tqdm import tqdm
from google import genai
from google.genai import types
from src.db_schema import DEFAULT_DB_PATH

def generate_macro_sentiment():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set. Please set it before running this script.")
        return

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Failed to initialize Gemini client: {e}")
        return

    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cur = conn.cursor()
    
    today = datetime.date.today().isoformat()
    
    print("Aggregating company sentiment scores to the sector level...")
    
    # 1. Fetch all company-level sentiments for today and join with their sector
    query = f"""
    SELECT 
        t.semiconductor_category as sector,
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
    WHERE s.date = '{today}'
    """
    
    df_raw = pd.read_sql_query(query, conn)
    
    if df_raw.empty:
        print(f"No company sentiment data found for today ({today}). Please run pipeline_ai_sentiment.py first.")
        conn.close()
        return
        
    # 2. Group by sector and average the scores
    df_sector = df_raw.groupby('sector').mean().reset_index()
    
    print(f"Generating AI Macro Overviews for {len(df_sector)} sectors using Gemini 3.1 Flash-Lite...")
    
    sector_updates = []
    
    # Define columns to summarize
    score_cols = [c for c in df_sector.columns if c != 'sector']
    
    for _, row in tqdm(df_sector.iterrows(), total=len(df_sector)):
        sector_name = row['sector']
        
        # Build a text representation of the sector's average scores
        score_context = f"Average Sentiment Scores for the {sector_name} sector:\n"
        for col in score_cols:
            score_context += f"- {col.replace('_', ' ').title()}: {row[col]:.2f}\n"
            
        prompt = f"""
        You are a highly analytical semiconductor macroeconomist.
        I have mathematically averaged the AI sentiment scores across all companies operating in the '{sector_name}' sub-sector of the semiconductor industry.
        
        {score_context}
        
        Instructions:
        Write a single, concise, professional paragraph summarizing the current market narrative for the {sector_name} sector based purely on these average sentiment scores.
        Highlight which themes are currently driving the sector (the highest positive scores) and which risks or drags are present (the lowest negative or highest risk scores).
        Do NOT use markdown headers or bold text. Keep it strictly readable plain text.
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            overview_text = response.text.strip()
            
            sector_updates.append((
                today, sector_name,
                row['general_sentiment_score'], row['ai_demand_sentiment'], row['data_center_sentiment'],
                row['hbm_sentiment'], row['foundry_capacity_sentiment'], row['semiconductor_capex_sentiment'],
                row['china_export_risk_sentiment'], row['inventory_sentiment'], row['gross_margin_sentiment'],
                row['pricing_pressure_sentiment'], row['automotive_demand_sentiment'], row['consumer_demand_sentiment'],
                row['industrial_demand_sentiment'], row['optical_networking_sentiment'], row['memory_pricing_sentiment'],
                row['analyst_sentiment'], row['management_tone_sentiment'], row['risk_sentiment'],
                overview_text
            ))
            
            time.sleep(4.1) # Respect 15 RPM
            
        except Exception as e:
            print(f"Error generating overview for sector {sector_name}: {e}")
            
    # Save sector data
    if sector_updates:
        cur.executemany('''
            INSERT OR REPLACE INTO sector_sentiment_daily (
                date, sector, general_sentiment_score, ai_demand_sentiment, data_center_sentiment, hbm_sentiment,
                foundry_capacity_sentiment, semiconductor_capex_sentiment, china_export_risk_sentiment, inventory_sentiment,
                gross_margin_sentiment, pricing_pressure_sentiment, automotive_demand_sentiment, consumer_demand_sentiment,
                industrial_demand_sentiment, optical_networking_sentiment, memory_pricing_sentiment, analyst_sentiment,
                management_tone_sentiment, risk_sentiment, sector_overview
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', sector_updates)
        conn.commit()
        
    print("Generating Total Semiconductor Market Macro Overview...")
    
    # 3. Compute Total Market Average (Average across ALL companies)
    market_row = df_raw.mean(numeric_only=True)
    
    market_score_context = "Average Sentiment Scores for the ENTIRE Semiconductor Market:\n"
    for col in score_cols:
        market_score_context += f"- {col.replace('_', ' ').title()}: {market_row[col]:.2f}\n"
        
    market_prompt = f"""
    You are a highly analytical semiconductor macroeconomist.
    I have mathematically averaged the AI sentiment scores across ALL companies across the ENTIRE semiconductor industry.
    
    {market_score_context}
    
    Instructions:
    Write a single, concise, professional paragraph summarizing the current macro market narrative for the overall Semiconductor Industry today based purely on these average sentiment scores.
    Identify the overarching dominant themes and the biggest systemic risks.
    Do NOT use markdown headers or bold text. Keep it strictly readable plain text.
    """
    
    try:
        market_response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=market_prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        macro_overview_text = market_response.text.strip()
        
        cur.execute('''
            INSERT OR REPLACE INTO market_sentiment_daily (
                date, general_sentiment_score, ai_demand_sentiment, data_center_sentiment, hbm_sentiment,
                foundry_capacity_sentiment, semiconductor_capex_sentiment, china_export_risk_sentiment, inventory_sentiment,
                gross_margin_sentiment, pricing_pressure_sentiment, automotive_demand_sentiment, consumer_demand_sentiment,
                industrial_demand_sentiment, optical_networking_sentiment, memory_pricing_sentiment, analyst_sentiment,
                management_tone_sentiment, risk_sentiment, macro_market_overview
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            today, market_row['general_sentiment_score'], market_row['ai_demand_sentiment'], market_row['data_center_sentiment'],
            market_row['hbm_sentiment'], market_row['foundry_capacity_sentiment'], market_row['semiconductor_capex_sentiment'],
            market_row['china_export_risk_sentiment'], market_row['inventory_sentiment'], market_row['gross_margin_sentiment'],
            market_row['pricing_pressure_sentiment'], market_row['automotive_demand_sentiment'], market_row['consumer_demand_sentiment'],
            market_row['industrial_demand_sentiment'], market_row['optical_networking_sentiment'], market_row['memory_pricing_sentiment'],
            market_row['analyst_sentiment'], market_row['management_tone_sentiment'], market_row['risk_sentiment'],
            macro_overview_text
        ))
        conn.commit()
        print("Total Market Macro Overview generated and saved!")
        
    except Exception as e:
        print(f"Error generating market overview: {e}")
        
    conn.close()

if __name__ == "__main__":
    generate_macro_sentiment()
