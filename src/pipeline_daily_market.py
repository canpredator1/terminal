import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from tqdm import tqdm

from src.db_schema import DEFAULT_DB_PATH
from src.tickers import TICKERS

def populate_daily_market():
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cur = conn.cursor()
    
    benchmarks = ['SPY', 'QQQ', 'IWM', 'SMH', 'SOXX', '^VIX', 'DX-Y.NYB', '^TNX', 'NVDA']
    all_tickers = list(set(TICKERS + benchmarks))
    
    print(f"Downloading 3 years of daily data for {len(all_tickers)} tickers...")
    # Group by ticker makes it easier to process
    data = yf.download(all_tickers, period='3y', group_by='ticker', auto_adjust=False, progress=False)
    
    # Process benchmarks first
    print("Processing market context...")
    context_rows = []
    
    spy = data['SPY'] if 'SPY' in data else pd.DataFrame()
    qqq = data['QQQ'] if 'QQQ' in data else pd.DataFrame()
    iwm = data['IWM'] if 'IWM' in data else pd.DataFrame()
    smh = data['SMH'] if 'SMH' in data else pd.DataFrame()
    soxx = data['SOXX'] if 'SOXX' in data else pd.DataFrame()
    vix = data['^VIX'] if '^VIX' in data else pd.DataFrame()
    usd = data['DX-Y.NYB'] if 'DX-Y.NYB' in data else pd.DataFrame()
    tnx = data['^TNX'] if '^TNX' in data else pd.DataFrame()
    nvda = data['NVDA'] if 'NVDA' in data else pd.DataFrame()
    
    if not spy.empty:
        spy_ret = spy['Adj Close'].pct_change()
        qqq_ret = qqq['Adj Close'].pct_change() if not qqq.empty else pd.Series(index=spy.index)
        iwm_ret = iwm['Adj Close'].pct_change() if not iwm.empty else pd.Series(index=spy.index)
        smh_ret = smh['Adj Close'].pct_change() if not smh.empty else pd.Series(index=spy.index)
        soxx_ret = soxx['Adj Close'].pct_change() if not soxx.empty else pd.Series(index=spy.index)
        vix_lvl = vix['Close'] if not vix.empty else pd.Series(index=spy.index)
        vix_ret = vix['Close'].pct_change() if not vix.empty else pd.Series(index=spy.index)
        usd_ret = usd['Adj Close'].pct_change() if not usd.empty else pd.Series(index=spy.index)
        tnx_ret = tnx['Adj Close'].pct_change() if not tnx.empty else pd.Series(index=spy.index)
        
        smh_ret_20d = smh['Adj Close'].pct_change(20) if not smh.empty else pd.Series(index=spy.index)
        spy_20dma = spy['Adj Close'].rolling(20).mean() if not spy.empty else pd.Series(index=spy.index)
        
        # Calculate breadth
        print("Calculating breadth metrics...")
        semi_returns = pd.DataFrame(index=spy.index)
        semi_above_20d = pd.DataFrame(index=spy.index)
        
        for t in TICKERS:
            if t in data and not data[t].empty:
                try:
                    close = data[t]['Adj Close']
                    semi_returns[t] = close.pct_change()
                    semi_above_20d[t] = close > close.rolling(20).mean()
                except Exception:
                    pass
                    
        pct_green = (semi_returns > 0).mean(axis=1)
        pct_above_20 = semi_above_20d.mean(axis=1)
        
        for date in spy.index:
            if pd.isna(spy_ret.loc[date]): continue
            
            d_str = date.strftime('%Y-%m-%d')
            v_lvl = vix_lvl.loc[date] if date in vix_lvl else np.nan
            
            m_regime = 'neutral'
            if not pd.isna(v_lvl) and not pd.isna(spy_20dma.loc[date]):
                if spy['Adj Close'].loc[date] > spy_20dma.loc[date] and v_lvl < 20:
                    m_regime = 'risk_on'
                elif v_lvl > 30:
                    m_regime = 'risk_off'
                    
            s_regime = 'neutral'
            if date in smh_ret_20d and not pd.isna(smh_ret_20d.loc[date]):
                if smh_ret_20d.loc[date] > 0.05:
                    s_regime = 'expansion'
                elif smh_ret_20d.loc[date] < -0.05:
                    s_regime = 'contraction'
            
            # Simple risk score approximation
            risk_score = 0
            if not pd.isna(v_lvl):
                risk_score = (v_lvl - 20) / 10.0
                
            ai_score = 0
            if date in nvda.index and date in spy.index:
                try:
                    nvda_20 = nvda['Adj Close'].pct_change(20).loc[date]
                    spy_20 = spy['Adj Close'].pct_change(20).loc[date]
                    if not pd.isna(nvda_20) and not pd.isna(spy_20):
                        ai_score = nvda_20 - spy_20
                except: pass
                
            context_rows.append((
                d_str,
                float(spy_ret.loc[date]) if not pd.isna(spy_ret.loc[date]) else None,
                float(qqq_ret.loc[date]) if not pd.isna(qqq_ret.loc[date]) else None,
                float(iwm_ret.loc[date]) if not pd.isna(iwm_ret.loc[date]) else None,
                float(smh_ret.loc[date]) if not pd.isna(smh_ret.loc[date]) else None,
                float(soxx_ret.loc[date]) if not pd.isna(soxx_ret.loc[date]) else None,
                float(v_lvl) if not pd.isna(v_lvl) else None,
                float(vix_ret.loc[date]) if not pd.isna(vix_ret.loc[date]) else None,
                float(usd_ret.loc[date]) if not pd.isna(usd_ret.loc[date]) else None,
                float(tnx_ret.loc[date]) if not pd.isna(tnx_ret.loc[date]) else None,
                None, # nasdaq breadth
                float(pct_green.loc[date]) if date in pct_green else None,
                float(pct_green.loc[date]) if date in pct_green else None,
                float(pct_above_20.loc[date]) if date in pct_above_20 else None,
                m_regime, s_regime,
                float(risk_score), float(ai_score)
            ))
            
    cur.executemany('''
        INSERT OR REPLACE INTO market_context_daily (
            date, spy_return_1d, qqq_return_1d, iwm_return_1d, smh_return_1d, soxx_return_1d,
            vix_level, vix_change_1d, usd_index_return_1d, ten_year_yield_change_1d,
            nasdaq_market_breadth, semiconductor_breadth, percent_semis_green, percent_semis_above_20dma,
            market_regime, semiconductor_regime, risk_on_risk_off_score, ai_theme_strength_score
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', context_rows)
    
    # Process individual tickers
    print("Processing daily market state for all tickers...")
    
    daily_rows = []
    
    # Pre-calculate market regime dicts for quick lookup
    regime_dict = {r[0]: (r[14], r[15]) for r in context_rows}
    spy_ret_dict = spy_ret.to_dict() if not spy.empty else {}
    qqq_ret_dict = qqq_ret.to_dict() if not qqq.empty else {}
    smh_ret_dict = smh_ret.to_dict() if not smh.empty else {}
    
    for ticker in tqdm(TICKERS):
        if ticker not in data or data[ticker].empty:
            continue
            
        try:
            df = data[ticker].copy()
            if df.empty or len(df) < 5: continue
            
            # Simple imputation for missing values
            df.ffill(inplace=True)
            
            close = df['Close']
            adj = df['Adj Close']
            high = df['High']
            low = df['Low']
            open_p = df['Open']
            vol = df['Volume']
            
            ret_1d = adj.pct_change()
            ret_3d = adj.pct_change(3)
            ret_5d = adj.pct_change(5)
            ret_10d = adj.pct_change(10)
            ret_20d = adj.pct_change(20)
            ret_60d = adj.pct_change(60)
            
            prev_close = close.shift(1)
            gap = (open_p - prev_close) / prev_close * 100
            
            rng = high - low
            intra_rng = np.where(open_p > 0, rng / open_p * 100, 0)
            pos_rng = np.where(rng > 0, (close - low) / rng, 0.5)
            
            vol_20 = vol.rolling(20).mean()
            vol_60 = vol.rolling(60).mean()
            vratio_20 = np.where(vol_20 > 0, vol / vol_20, 1.0)
            vratio_60 = np.where(vol_60 > 0, vol / vol_60, 1.0)
            
            volat_20 = ret_1d.rolling(20).std() * np.sqrt(252)
            volat_60 = ret_1d.rolling(60).std() * np.sqrt(252)
            
            # Simplified ATR (close-to-close proxy for speed)
            tr = pd.DataFrame({'a': high-low, 'b': abs(high-prev_close), 'c': abs(low-prev_close)}).max(axis=1)
            atr_14 = tr.rolling(14).mean()
            
            # Just calculating some basic correlations instead of betas for speed
            corr_smh_60 = ret_1d.rolling(60).corr(smh_ret) if not smh.empty else pd.Series(index=df.index)
            
            for date in df.index:
                if pd.isna(ret_1d.loc[date]): continue
                d_str = date.strftime('%Y-%m-%d')
                
                m_regime, s_regime = regime_dict.get(d_str, ('neutral', 'neutral'))
                
                s_ret = spy_ret_dict.get(date, 0)
                sm_ret = smh_ret_dict.get(date, 0)
                q_ret = qqq_ret_dict.get(date, 0)
                
                t_ret = float(ret_1d.loc[date])
                
                dq_flag = 'ok'
                if vol.loc[date] < 1000: dq_flag = 'low_volume'
                elif gap.loc[date] > 10: dq_flag = 'price_gap'
                
                daily_rows.append((
                    d_str, ticker,
                    float(open_p.loc[date]), float(high.loc[date]), float(low.loc[date]),
                    float(close.loc[date]), float(adj.loc[date]),
                    float(vol.loc[date]), float(vol.loc[date] * close.loc[date]),
                    t_ret,
                    float(ret_3d.loc[date]) if not pd.isna(ret_3d.loc[date]) else None,
                    float(ret_5d.loc[date]) if not pd.isna(ret_5d.loc[date]) else None,
                    float(ret_10d.loc[date]) if not pd.isna(ret_10d.loc[date]) else None,
                    float(ret_20d.loc[date]) if not pd.isna(ret_20d.loc[date]) else None,
                    float(ret_60d.loc[date]) if not pd.isna(ret_60d.loc[date]) else None,
                    float(gap.loc[date]) if not pd.isna(gap.loc[date]) else None,
                    float(intra_rng[df.index.get_loc(date)]) if not pd.isna(intra_rng[df.index.get_loc(date)]) else None,
                    float(pos_rng[df.index.get_loc(date)]) if not pd.isna(pos_rng[df.index.get_loc(date)]) else None,
                    float(vratio_20[df.index.get_loc(date)]) if not pd.isna(vratio_20[df.index.get_loc(date)]) else None,
                    float(vratio_60[df.index.get_loc(date)]) if not pd.isna(vratio_60[df.index.get_loc(date)]) else None,
                    float(volat_20.loc[date]) if not pd.isna(volat_20.loc[date]) else None,
                    float(volat_60.loc[date]) if not pd.isna(volat_60.loc[date]) else None,
                    float(atr_14.loc[date]) if not pd.isna(atr_14.loc[date]) else None,
                    None, None, None, # betas
                    None, None,
                    float(corr_smh_60.loc[date]) if not pd.isna(corr_smh_60.loc[date]) else None,
                    None, None, # corrs
                    None, None, None, None, None, None, # RS
                    t_ret - (s_ret if not pd.isna(s_ret) else 0),
                    t_ret - (q_ret if not pd.isna(q_ret) else 0),
                    t_ret - (sm_ret if not pd.isna(sm_ret) else 0),
                    None, None, None, None, # other abnormals
                    m_regime, s_regime, None, # regimes
                    dq_flag
                ))
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    print(f"Inserting {len(daily_rows)} rows into ticker_daily_market_state...")
    # Insert in chunks to avoid SQLite limits
    chunk_size = 10000
    for i in range(0, len(daily_rows), chunk_size):
        cur.executemany('''
            INSERT OR REPLACE INTO ticker_daily_market_state (
                date, ticker, open, high, low, close, adjusted_close, volume, dollar_volume,
                return_1d, return_3d, return_5d, return_10d, return_20d, return_60d,
                gap_percent, intraday_range_percent, close_position_in_daily_range,
                volume_ratio_20d, volume_ratio_60d, volatility_20d, volatility_60d, atr_14d,
                rolling_beta_vs_spy_60d, rolling_beta_vs_qqq_60d, rolling_beta_vs_smh_60d,
                rolling_correlation_vs_spy_60d, rolling_correlation_vs_qqq_60d,
                rolling_correlation_vs_smh_60d, rolling_correlation_vs_nvda_60d,
                rolling_correlation_vs_soxx_60d, relative_strength_vs_spy_5d,
                relative_strength_vs_qqq_5d, relative_strength_vs_smh_5d,
                relative_strength_vs_spy_20d, relative_strength_vs_qqq_20d,
                relative_strength_vs_smh_20d, abnormal_return_vs_spy_1d,
                abnormal_return_vs_qqq_1d, abnormal_return_vs_smh_1d,
                abnormal_return_vs_soxx_1d, abnormal_return_vs_theme_basket_1d,
                abnormal_return_vs_smh_3d, abnormal_return_vs_smh_5d,
                market_regime, semiconductor_regime, theme_regime, data_quality_flag
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', daily_rows[i:i+chunk_size])
    
    conn.commit()
    conn.close()
    print("Done populating daily market state.")

if __name__ == '__main__':
    populate_daily_market()
