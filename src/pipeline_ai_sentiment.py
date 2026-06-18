import os
import sqlite3
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import datetime
import json
import time
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from src.db_schema import DEFAULT_DB_PATH

def generate_ai_sentiment():
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
    
    # Get all tickers
    df_tickers = pd.read_sql_query("SELECT ticker, company_name FROM ticker_master", conn)
    
    today = datetime.date.today().isoformat()
    
    # Filter to only tickers that don't have sentiment for today
    existing_sent = pd.read_sql_query(f"SELECT ticker FROM sentiment_daily WHERE date='{today}'", conn)['ticker'].tolist()
    df_tickers = df_tickers[~df_tickers['ticker'].isin(existing_sent)]
    
    if df_tickers.empty:
        print("All tickers already have sentiment for today.")
        return

    print(f"Generating FULL-TEXT AI Sentiment for {len(df_tickers)} companies using Gemini 3.1 Flash Lite...")
    
    updates = []
    failed_tickers = []
    
    # Request headers to bypass simple bot checks
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for _, row in tqdm(df_tickers.iterrows(), total=len(df_tickers)):
        ticker = row['ticker']
        company_name = row['company_name']
        
        # Fetch recent news URLs for this ticker
        df_news = pd.read_sql_query(
            "SELECT headline, source, url, published_at FROM news_events WHERE ticker=? AND is_company_specific=1 ORDER BY published_at DESC LIMIT 10",
            conn,
            params=(ticker,),
        )
        
        news_count = len(df_news)
        news_context = ""
        
        if not df_news.empty:
            news_context = f"Below is the FULL TEXT of the {news_count} most recent news articles for {company_name} ({ticker}):\n\n"
            
            for i, n_row in df_news.iterrows():
                try:
                    # Attempt to scrape the full text of the article
                    html = requests.get(n_row['url'], headers=headers, timeout=5).text
                    soup = BeautifulSoup(html, 'html.parser')
                    # Extract paragraphs, ignoring super short ones (usually ads/nav)
                    paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
                    article_text = "\\n".join(paragraphs)
                    
                    news_context += f"--- ARTICLE {i+1} ---\n"
                    news_context += f"HEADLINE: {n_row['headline']}\n"
                    news_context += f"DATE: {n_row['published_at']} | SOURCE: {n_row['source']}\n"
                    news_context += f"FULL TEXT:\n{article_text}\n\n"
                except Exception as e:
                    # Fallback to just the headline if the scrape fails
                    news_context += f"--- ARTICLE {i+1} ---\n"
                    news_context += f"HEADLINE: {n_row['headline']}\n"
                    news_context += f"DATE: {n_row['published_at']} | SOURCE: {n_row['source']}\n"
                    news_context += f"(Failed to extract full text, rely on headline)\n\n"
        else:
            news_context = "No recent news available."
            
        prompt = f"""
        You are a highly analytical semiconductor financial analyst. 
        Analyze the following FULL TEXT news articles for {company_name} ({ticker}) and extract thematic sentiment scores.
        Because you have the full text, look deeply for subtle nuances regarding the following themes.
        
        {news_context}
        
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
                model='gemini-3.1-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            raw_text = response.text.strip()
            data = json.loads(raw_text)
                
            updates.append((
                today, ticker, 
                data.get("general_sentiment_score", 0.0), data.get("general_sentiment_label", "neutral"),
                news_count,
                data.get("ai_demand_sentiment", 0.0), data.get("data_center_sentiment", 0.0), data.get("hbm_sentiment", 0.0),
                data.get("foundry_capacity_sentiment", 0.0), data.get("semiconductor_capex_sentiment", 0.0),
                data.get("china_export_risk_sentiment", 0.0), data.get("inventory_sentiment", 0.0),
                data.get("gross_margin_sentiment", 0.0), data.get("pricing_pressure_sentiment", 0.0),
                data.get("automotive_demand_sentiment", 0.0), data.get("consumer_demand_sentiment", 0.0),
                data.get("industrial_demand_sentiment", 0.0), data.get("optical_networking_sentiment", 0.0),
                data.get("memory_pricing_sentiment", 0.0), data.get("analyst_sentiment", 0.0),
                data.get("management_tone_sentiment", 0.0), data.get("risk_sentiment", 0.0),
                data.get("sentiment_summary", "No clear sentiment available.")
            ))
            
        except Exception as e:
            print(f"Error generating sentiment for {ticker}: {e}")
            failed_tickers.append(row)
            
        # Gemini 3.1 Flash Lite allows 15 RPM. We sleep for 4.1 seconds to be safe.
        time.sleep(4.1)
        
    # Retry failed tickers once at the end
    if failed_tickers:
        print(f"Retrying {len(failed_tickers)} failed companies...")
        time.sleep(10) # Give the API a brief rest before retrying
        
        for row in failed_tickers:
            ticker = row['ticker']
            company_name = row['company_name']
            
            # Re-fetch news
            df_news = pd.read_sql_query(
                "SELECT headline, source, url, published_at FROM news_events WHERE ticker=? AND is_company_specific=1 ORDER BY published_at DESC LIMIT 10",
                conn,
                params=(ticker,),
            )
            news_count = len(df_news)
            news_context = ""
            
            if not df_news.empty:
                news_context = f"Below is the FULL TEXT of the {news_count} most recent news articles for {company_name} ({ticker}):\n\n"
                for i, n_row in df_news.iterrows():
                    try:
                        html = requests.get(n_row['url'], headers=headers, timeout=5).text
                        soup = BeautifulSoup(html, 'html.parser')
                        paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
                        article_text = "\\n".join(paragraphs)
                        news_context += f"--- ARTICLE {i+1} ---\nHEADLINE: {n_row['headline']}\nDATE: {n_row['published_at']} | SOURCE: {n_row['source']}\nFULL TEXT:\n{article_text}\n\n"
                    except Exception:
                        news_context += f"--- ARTICLE {i+1} ---\nHEADLINE: {n_row['headline']}\nDATE: {n_row['published_at']} | SOURCE: {n_row['source']}\n(Failed to extract full text, rely on headline)\n\n"
            else:
                news_context = "No recent news available."
                
            prompt = f"""
            You are a highly analytical semiconductor financial analyst. 
            Analyze the following FULL TEXT news articles for {company_name} ({ticker}) and extract thematic sentiment scores.
            Because you have the full text, look deeply for subtle nuances regarding the following themes.
            
            {news_context}
            
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
                    model='gemini-3.1-flash-lite',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                data = json.loads(response.text.strip())
                updates.append((
                    today, ticker, 
                    data.get("general_sentiment_score", 0.0), data.get("general_sentiment_label", "neutral"),
                    news_count,
                    data.get("ai_demand_sentiment", 0.0), data.get("data_center_sentiment", 0.0), data.get("hbm_sentiment", 0.0),
                    data.get("foundry_capacity_sentiment", 0.0), data.get("semiconductor_capex_sentiment", 0.0),
                    data.get("china_export_risk_sentiment", 0.0), data.get("inventory_sentiment", 0.0),
                    data.get("gross_margin_sentiment", 0.0), data.get("pricing_pressure_sentiment", 0.0),
                    data.get("automotive_demand_sentiment", 0.0), data.get("consumer_demand_sentiment", 0.0),
                    data.get("industrial_demand_sentiment", 0.0), data.get("optical_networking_sentiment", 0.0),
                    data.get("memory_pricing_sentiment", 0.0), data.get("analyst_sentiment", 0.0),
                    data.get("management_tone_sentiment", 0.0), data.get("risk_sentiment", 0.0),
                    data.get("sentiment_summary", "No clear sentiment available.")
                ))
            except Exception as e:
                print(f"Retry failed for {ticker}: {e}")
                
            time.sleep(4.1)
            
    if updates:
        cur.executemany('''
            INSERT OR REPLACE INTO sentiment_daily (
                date, ticker, general_sentiment_score, general_sentiment_label, news_count,
                ai_demand_sentiment, data_center_sentiment, hbm_sentiment, foundry_capacity_sentiment,
                semiconductor_capex_sentiment, china_export_risk_sentiment, inventory_sentiment,
                gross_margin_sentiment, pricing_pressure_sentiment, automotive_demand_sentiment,
                consumer_demand_sentiment, industrial_demand_sentiment, optical_networking_sentiment,
                memory_pricing_sentiment, analyst_sentiment, management_tone_sentiment,
                risk_sentiment, sentiment_summary
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', updates)
        conn.commit()
        print(f"Successfully generated and saved FULL-TEXT AI Sentiment for {len(updates)} companies!")
    
    conn.close()

if __name__ == "__main__":
    generate_ai_sentiment()
