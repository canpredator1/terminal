import sqlite3
import pandas as pd
import yfinance as yf
from pathlib import Path
from tqdm import tqdm
import datetime
import requests

from src.db_schema import DEFAULT_DB_PATH
from src.news_relevance import classify_news, extract_yahoo_related_tickers
from src.tickers import TICKERS

def get_simple_sentiment(text):
    """Very basic sentiment score without external ML libraries to avoid dependencies"""
    if not text: return 0.0
    text = text.lower()
    positive_words = ['up', 'high', 'growth', 'beat', 'gain', 'jump', 'surge', 'strong', 'positive', 'win', 'bullish', 'upgrade', 'buy']
    negative_words = ['down', 'low', 'decline', 'miss', 'loss', 'drop', 'fall', 'weak', 'negative', 'bearish', 'downgrade', 'sell', 'risk']
    
    pos_count = sum(text.count(w) for w in positive_words)
    neg_count = sum(text.count(w) for w in negative_words)
    
    total = pos_count + neg_count
    if total == 0: return 0.0
    return (pos_count - neg_count) / total

def populate_secondary():
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cur = conn.cursor()
    
    print("Populating secondary tables (Fundamentals, Valuation, Calendar, Sentiment)...")
    
    today = datetime.date.today().isoformat()
    
    fun_rows = []
    val_rows = []
    cal_rows = []
    sen_rows = []
    own_rows = []
    news_rows = []
    
    for ticker in tqdm(TICKERS):
        try:
            t = yf.Ticker(ticker)
            info = t.info
            company_name = info.get('longName') or info.get('shortName') or ticker
            
            # Valuation snapshot
            val_rows.append((
                today, ticker,
                info.get('marketCap'), info.get('enterpriseValue'),
                info.get('priceToSalesTrailing12Months'), info.get('forwardPE') * info.get('forwardEps') / info.get('revenuePerShare') if info.get('forwardPE') and info.get('forwardEps') and info.get('revenuePerShare') else None,
                info.get('trailingPE'), info.get('forwardPE'),
                info.get('enterpriseToRevenue'), info.get('enterpriseToEbitda'),
                info.get('priceToBook'), None, # FCF yield
                None, None, # forward growth
                None, None, None # percentiles/risk
            ))
            
            # Calendar events
            cal = t.calendar
            if isinstance(cal, dict) and 'Earnings Date' in cal:
                edates = cal['Earnings Date']
                if edates:
                    edate = edates[0].strftime('%Y-%m-%d') if hasattr(edates[0], 'strftime') else str(edates[0])
                    cal_rows.append((
                        f"{ticker}_earnings_{edate}", ticker, edate, 'earnings_report', None, 0.8,
                        "Earnings Release", None, None, 0, 0
                    ))
            elif hasattr(cal, 'iloc'):
                # DataFrame format
                if 'Earnings Date' in cal.index:
                    dates = cal.loc['Earnings Date']
                    if len(dates) > 0 and pd.notna(dates.iloc[0]):
                        edate = dates.iloc[0].strftime('%Y-%m-%d') if hasattr(dates.iloc[0], 'strftime') else str(dates.iloc[0])
                        cal_rows.append((
                            f"{ticker}_earnings_{edate}", ticker, edate, 'earnings_report', None, 0.8,
                            "Earnings Release", None, None, 0, 0
                        ))
                            
            # Fundamentals Quarterly (just grabbing the most recent to avoid massive downloads)
            qf = t.quarterly_financials
            if hasattr(qf, 'columns') and not qf.empty:
                for date_col in qf.columns[:4]: # last 4 quarters
                    date_str = date_col.strftime('%Y-%m-%d')
                    col = qf[date_col]
                    
                    rev = col.get('Total Revenue')
                    gp = col.get('Gross Profit')
                    oi = col.get('Operating Income')
                    ni = col.get('Net Income')
                    
                    fun_rows.append((
                        ticker, date_str[:4], None, date_str,
                        float(rev) if pd.notna(rev) else None, None, None,
                        float(gp) if pd.notna(gp) else None, float(gp/rev) if pd.notna(gp) and pd.notna(rev) and rev>0 else None,
                        float(oi) if pd.notna(oi) else None, float(oi/rev) if pd.notna(oi) and pd.notna(rev) and rev>0 else None,
                        float(ni) if pd.notna(ni) else None, float(ni/rev) if pd.notna(ni) and pd.notna(rev) and rev>0 else None,
                        None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None
                    ))
            
            # Sentiment from News using yfinance
            news = t.news
            if news:
                parsed_news = []
                for n in news:
                    c = n.get('content', n) # fallback to flat if old format
                    related_tickers = extract_yahoo_related_tickers(c)
                    parsed_news.append({
                        'title': c.get('title', ''),
                        'summary': c.get('summary', ''),
                        'pub_date': c.get('pubDate', today),
                        'source': (c.get('provider') or {}).get('displayName', 'Yahoo Finance'),
                        'url': (c.get('clickThroughUrl') or {}).get('url', ''),
                        'related_tickers': related_tickers
                    })
                
                # We no longer generate naive sentiment here; handled by pipeline_ai_sentiment.py
                
                for pn in parsed_news:
                    import uuid
                    nid = str(uuid.uuid4())
                    flags = classify_news(
                        ticker,
                        company_name,
                        pn['title'],
                        pn['summary'],
                        pn['related_tickers'],
                    )
                    news_rows.append((
                        nid, pn['pub_date'], ticker, pn['title'], pn['source'],
                        pn['url'], 'general', 0.5, 0.0, # default 0.0 sentiment
                        flags['topic_tags'], '', flags['related_tickers'], flags['is_company_specific'],
                        flags['is_sector_wide'], flags['is_macro_related'], pn['summary'],
                        '', flags['data_quality_flag']
                    ))
                
            # Ownership
            own_rows.append((
                today, ticker,
                info.get('shortPercentOfFloat'), None,
                info.get('heldPercentInstitutions'), info.get('heldPercentInsiders'),
                None, None, None, None, None, None, None, None, None
            ))
            
        except Exception as e:
            print(f"Error on secondary data for {ticker}: {e}")
            
    # Inserts
    cur.executemany('''
        INSERT OR REPLACE INTO valuation_snapshot (
            date, ticker, market_cap, enterprise_value, price_to_sales_ttm, price_to_sales_forward,
            price_to_earnings_ttm, price_to_earnings_forward, ev_to_sales, ev_to_ebitda,
            price_to_book, free_cash_flow_yield, revenue_growth_forward, eps_growth_forward,
            valuation_percentile_1y, valuation_percentile_3y, valuation_risk_score
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', val_rows)
    
    cur.executemany('''
        INSERT OR REPLACE INTO calendar_events (
            event_id, ticker, event_date, event_type, event_time, event_importance_score,
            description, related_tickers, expected_topics, is_before_market, is_after_market
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    ''', cal_rows)
    
    cur.executemany('''
        INSERT OR REPLACE INTO fundamentals_quarterly (
            ticker, fiscal_year, fiscal_quarter, period_end_date, revenue, revenue_growth_yoy,
            revenue_growth_qoq, gross_profit, gross_margin, operating_income, operating_margin,
            net_income, net_margin, eps_diluted, free_cash_flow, free_cash_flow_margin,
            cash_and_equivalents, total_debt, net_debt, debt_to_equity, inventory,
            inventory_growth_yoy, inventory_days, capex, capex_growth_yoy, r_and_d_expense,
            r_and_d_as_percent_revenue, accounts_receivable, days_sales_outstanding,
            backlog, book_to_bill, fundamental_quality_score
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', fun_rows)
    
    # sentiment_daily insert removed; handled by pipeline_ai_sentiment.py
    cur.executemany('''
        INSERT OR REPLACE INTO ownership_flow_optional (
            date, ticker, short_interest_percent_float, days_to_cover, institutional_ownership_percent,
            insider_ownership_percent, recent_insider_buying, recent_insider_selling,
            etf_ownership_percent, largest_etf_holders, options_volume, put_call_ratio,
            implied_volatility, iv_percentile_1y, flow_risk_score
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', own_rows)
    
    cur.executemany('''
        INSERT OR REPLACE INTO news_events (
            news_id, published_at, ticker, headline, source, url, news_category,
            news_importance_score, sentiment_score, topic_tags, mentioned_companies,
            related_tickers, is_company_specific, is_sector_wide, is_macro_related,
            summary, possible_market_impact, data_quality_flag
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', news_rows)
    
    conn.commit()
    conn.close()
    print("Done populating secondary tables.")

if __name__ == '__main__':
    populate_secondary()
