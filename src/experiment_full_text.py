import os
import sqlite3
import pandas as pd
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
import json
from src.db_schema import DEFAULT_DB_PATH

def run_experiment():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        return

    client = genai.Client(api_key=api_key)
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    
    ticker = "AMD"
    company_name = "Advanced Micro Devices, Inc."
    
    print(f"=== Running Full-Text Experiment for {ticker} ===")
    
    df_news = pd.read_sql_query(f"""
        SELECT headline, url, published_at, source 
        FROM news_events 
        WHERE ticker='{ticker}' 
        ORDER BY published_at DESC LIMIT 10
    """, conn)
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    massive_context = f"Below is the FULL TEXT of the 10 most recent news articles for {company_name} ({ticker}):\n\n"
    
    for i, row in df_news.iterrows():
        print(f"Scraping [{i+1}/10]: {row['headline']}")
        try:
            html = requests.get(row['url'], headers=headers, timeout=10).text
            soup = BeautifulSoup(html, 'html.parser')
            # Extract paragraphs, ignoring super short ones (usually ads/nav)
            paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
            article_text = "\n".join(paragraphs)
            
            massive_context += f"--- ARTICLE {i+1} ---\n"
            massive_context += f"HEADLINE: {row['headline']}\n"
            massive_context += f"DATE: {row['published_at']} | SOURCE: {row['source']}\n"
            massive_context += f"FULL TEXT:\n{article_text}\n\n"
        except Exception as e:
            print(f"  -> Failed to scrape: {e}")
            
    print(f"\nConstructed massive context of length: {len(massive_context)} characters.")
    print("Sending this entire block of text to Gemini 2.5 Flash for deep analysis...")
    
    prompt = f"""
    You are a highly analytical semiconductor financial analyst. 
    Analyze the following FULL TEXT news articles for {company_name} ({ticker}) and extract thematic sentiment scores.
    Because you have the full text, look deeply for subtle nuances regarding the following themes.
    
    {massive_context}
    
    Provide your analysis STRICTLY as a JSON object.
    Scores must be floats between -1.0 (very negative) and 1.0 (very positive). If a theme is not mentioned or not applicable, set it to 0.0.
    
    Required JSON keys:
    - "general_sentiment_score": float (-1.0 to 1.0)
    - "general_sentiment_label": string ("positive", "neutral", "negative")
    - "ai_demand_sentiment": float
    - "data_center_sentiment": float
    - "hbm_sentiment": float
    - "foundry_capacity_sentiment": float
    - "semiconductor_capex_sentiment": float
    - "china_export_risk_sentiment": float
    - "inventory_sentiment": float
    - "gross_margin_sentiment": float
    - "pricing_pressure_sentiment": float
    - "automotive_demand_sentiment": float
    - "consumer_demand_sentiment": float
    - "industrial_demand_sentiment": float
    - "optical_networking_sentiment": float
    - "memory_pricing_sentiment": float
    - "analyst_sentiment": float
    - "management_tone_sentiment": float
    - "risk_sentiment": float (0.0 means low risk, 1.0 means high risk. ONLY THIS ONE IS 0 to 1)
    - "sentiment_summary": string (A concise 1-sentence summary of the sentiment)
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        print("\n=== GEMINI FULL-TEXT RESULTS ===")
        parsed = json.loads(response.text)
        print(json.dumps(parsed, indent=2))
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        
if __name__ == "__main__":
    run_experiment()
