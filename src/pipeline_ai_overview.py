import os
import sqlite3
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import time
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from src.db_schema import DEFAULT_DB_PATH

def generate_ai_overviews():
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
    
    # Get all tickers that don't have an overview yet or failed previously
    df_tickers = pd.read_sql_query("SELECT ticker, company_name, company_description FROM ticker_master WHERE ai_overview IS NULL OR ai_overview LIKE '%temporarily unavailable%'", conn)
    
    if df_tickers.empty:
        print("All tickers already have overviews.")
        conn.close()
        return

    print(f"Generating FULL-TEXT AI overviews for {len(df_tickers)} companies using Gemini 3.1 Flash Lite...")
    
    updates = []
    failed_tickers = []
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for _, row in tqdm(df_tickers.iterrows(), total=len(df_tickers)):
        ticker = row['ticker']
        company_name = row['company_name']
        company_desc = row['company_description'] or ""
        
        # Fetch recent news URLs for this ticker
        df_news = pd.read_sql_query(f"SELECT headline, source, url, published_at FROM news_events WHERE ticker='{ticker}' ORDER BY published_at DESC LIMIT 10", conn)
        
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
                    
                    news_context += f"--- ARTICLE {i+1} ---\n"
                    news_context += f"HEADLINE: {n_row['headline']}\n"
                    news_context += f"DATE: {n_row['published_at']} | SOURCE: {n_row['source']}\n"
                    news_context += f"FULL TEXT:\n{article_text}\n\n"
                except Exception as e:
                    news_context += f"--- ARTICLE {i+1} ---\n"
                    news_context += f"HEADLINE: {n_row['headline']}\n"
                    news_context += f"DATE: {n_row['published_at']} | SOURCE: {n_row['source']}\n"
                    news_context += f"(Failed to extract full text, rely on headline)\n\n"
        else:
            news_context = "No recent news available."
            
        prompt = f"""
        You are a highly analytical semiconductor industry expert. 
        Write a concise, 2-paragraph "AI Overview" for {company_name} ({ticker}).
        
        Company Context: {company_desc[:500]}...
        
        {news_context}
        
        Instructions:
        1. First paragraph: Briefly explain what this company does and its specific role in the semiconductor supply chain (e.g., foundry, fabless, equipment, memory, analog).
        2. Second paragraph: Summarize their current market narrative or sentiment based on the massive full-text news provided. If there is no news, state their general market position.
        3. Do NOT use markdown headers or bold text. Keep it strictly readable plain text.
        4. Tone should be professional, objective, and insightful, exactly like a premium financial analyst report.
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3
                )
            )
            overview_text = response.text.strip()
            updates.append((overview_text, ticker))
            
        except Exception as e:
            print(f"Error generating overview for {ticker}: {e}")
            failed_tickers.append(row)
            
        # Gemini 3.1 Flash Lite allows 15 RPM. We sleep for 4.1 seconds to be safe.
        time.sleep(4.1)
            
    # Retry failed tickers once at the end
    if failed_tickers:
        print(f"Retrying {len(failed_tickers)} failed companies...")
        time.sleep(10)
        
        for row in failed_tickers:
            ticker = row['ticker']
            company_name = row['company_name']
            company_desc = row['company_description'] or ""
            
            df_news = pd.read_sql_query(f"SELECT headline, source, url, published_at FROM news_events WHERE ticker='{ticker}' ORDER BY published_at DESC LIMIT 10", conn)
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
            You are a highly analytical semiconductor industry expert. 
            Write a concise, 2-paragraph "AI Overview" for {company_name} ({ticker}).
            
            Company Context: {company_desc[:500]}...
            
            {news_context}
            
            Instructions:
            1. First paragraph: Briefly explain what this company does and its specific role in the semiconductor supply chain (e.g., foundry, fabless, equipment, memory, analog).
            2. Second paragraph: Summarize their current market narrative or sentiment based on the massive full-text news provided. If there is no news, state their general market position.
            3. Do NOT use markdown headers or bold text. Keep it strictly readable plain text.
            4. Tone should be professional, objective, and insightful, exactly like a premium financial analyst report.
            """
            
            try:
                response = client.models.generate_content(
                    model='gemini-3.1-flash-lite',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3
                    )
                )
                overview_text = response.text.strip()
                updates.append((overview_text, ticker))
            except Exception as e:
                print(f"Retry failed for {ticker}: {e}")
                updates.append((f"AI Overview temporarily unavailable for {ticker}.", ticker))
                
            time.sleep(4.1)

    # Save back to database
    if updates:
        cur = conn.cursor()
        cur.executemany("UPDATE ticker_master SET ai_overview = ? WHERE ticker = ?", updates)
        conn.commit()
        print(f"AI Overviews successfully generated and saved to the database for {len(updates)} companies!")
        
    conn.close()

if __name__ == "__main__":
    generate_ai_overviews()
