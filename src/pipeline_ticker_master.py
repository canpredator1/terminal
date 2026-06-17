import sqlite3
import pandas as pd
import yfinance as yf
from pathlib import Path
from tqdm import tqdm

from src.db_schema import DEFAULT_DB_PATH
from src.tickers import TICKERS
from src.relationships import COMPANY_TAGS, BASE_COMPANIES

SEMICONDUCTOR_SUBCATEGORY = {
    'NVDA': 'ai_gpu_accelerator',
    'AMD': 'cpu_gpu_processor',
    'AVGO': 'networking_broadband',
    'QCOM': 'rf_wireless_mobile',
    'INTC': 'cpu_processor',
    'ADI': 'analog_mixed_signal',
    'MCHP': 'mcu_analog',
    'NXPI': 'automotive_industrial',
    'TXN': 'analog_embedded',
    'ON': 'power_analog',
    'MPWR': 'power_management',
    'MRVL': 'networking_custom_silicon',
    'ALAB': 'optical_networking',
    'LSCC': 'fpga_programmable',
    'SLAB': 'iot_mixed_signal',
    'SWKS': 'rf_wireless',
    'QRVO': 'rf_wireless',
    'SYNA': 'human_interface',
    'SITM': 'networking_timing',
    'DIOD': 'discrete_analog',
    'ALGM': 'power_sensing',
    'AMBA': 'ai_vision_processor',
    'CRUS': 'audio_mixed_signal',
    'AOSL': 'power_mosfet',
    'SMTC': 'analog_mixed_signal',
    'SIMO': 'power_management',
    'PXLW': 'display_driver',
    'INDI': 'automotive_radar',
    'MXL': 'data_infrastructure',
    'MTSI': 'rf_photonics',
    'RMBS': 'memory_interface_ip',
    'HIMX': 'display_driver',
    'NVTS': 'power_gan',
    'NVEC': 'spintronics_sensor',
    'GSIT': 'memory_mram',
}

def get_business_role(category: str) -> str:
    if category in ['foundry', 'memory', 'semiconductor'] or category in SEMICONDUCTOR_SUBCATEGORY.values():
        return 'chip_maker'
    elif category == 'equipment':
        return 'equipment_supplier'
    elif category == 'ip':
        return 'ip_licensor'
    elif category == 'assembly':
        return 'osat_ems'
    elif category == 'server':
        return 'system_integrator'
    elif category == 'device':
        return 'device_maker'
    elif category == 'energy':
        return 'energy_semiconductor'
    return 'other'

def get_exposure_scores(category: str):
    scores = {
        'ai': 0.0, 'data_center': 0.0, 'consumer': 0.0, 'automotive': 0.0, 
        'industrial': 0.0, 'china': 0.0, 'memory': 0.0, 'foundry': 0.0, 
        'equipment': 0.0, 'optical': 0.0
    }
    
    if category == 'ai_gpu_accelerator':
        scores.update({'ai': 0.95, 'data_center': 0.9, 'consumer': 0.25})
    elif category in ['cpu_gpu_processor', 'cpu_processor']:
        scores.update({'ai': 0.5, 'data_center': 0.8, 'consumer': 0.6})
    elif category == 'foundry':
        scores.update({'foundry': 0.9, 'ai': 0.7})
    elif category == 'equipment':
        scores.update({'equipment': 0.9, 'ai': 0.5, 'memory': 0.4, 'foundry': 0.5})
    elif category in ['memory', 'memory_mram']:
        scores.update({'memory': 0.9, 'ai': 0.6, 'data_center': 0.6})
    elif category == 'memory_interface_ip':
        scores.update({'memory': 0.8, 'data_center': 0.7})
    elif category in ['networking_broadband', 'networking_custom_silicon', 'data_infrastructure', 'networking_timing']:
        scores.update({'data_center': 0.8, 'ai': 0.4, 'industrial': 0.3})
    elif category in ['analog_mixed_signal', 'mcu_analog', 'analog_embedded', 'discrete_analog', 'power_sensing', 'iot_mixed_signal']:
        scores.update({'automotive': 0.7, 'industrial': 0.8, 'consumer': 0.4})
    elif category in ['power_analog', 'power_management', 'power_mosfet', 'power_gan']:
        scores.update({'automotive': 0.8, 'industrial': 0.7, 'consumer': 0.3})
    elif category in ['rf_wireless', 'rf_wireless_mobile', 'rf_photonics']:
        scores.update({'consumer': 0.8, 'automotive': 0.3})
    elif category in ['automotive_industrial', 'automotive_radar', 'spintronics_sensor']:
        scores.update({'automotive': 0.9, 'industrial': 0.7})
    elif category in ['optical_networking', 'optical']:
        scores.update({'optical': 0.9, 'data_center': 0.8})
    elif category in ['human_interface', 'display_driver', 'audio_mixed_signal']:
        scores.update({'consumer': 0.9, 'automotive': 0.4})
    elif category == 'fpga_programmable':
        scores.update({'industrial': 0.8, 'data_center': 0.5, 'automotive': 0.4})
    elif category == 'ai_vision_processor':
        scores.update({'ai': 0.8, 'automotive': 0.6, 'consumer': 0.4})
    elif category in ['assembly_packaging', 'assembly']:
        scores.update({'foundry': 0.6, 'consumer': 0.5, 'automotive': 0.4})
    elif category == 'ip_licensing':
        scores.update({'data_center': 0.6, 'consumer': 0.6})
        
    return scores

def get_risk_bucket(market_cap):
    if market_cap is None:
        return 'unknown'
    if market_cap > 200e9:
        return 'mega_cap'
    elif market_cap > 10e9:
        return 'large_cap'
    elif market_cap > 2e9:
        return 'mid_cap'
    elif market_cap > 300e6:
        return 'small_cap'
    else:
        return 'micro_cap'

def populate_ticker_master():
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cur = conn.cursor()
    
    print(f"Fetching data for {len(TICKERS)} tickers...")
    
    rows = []
    for ticker in tqdm(TICKERS):
        try:
            info = yf.Ticker(ticker).info
            
            # Map category
            old_tag = COMPANY_TAGS.get(ticker, 'other')
            if old_tag == 'semiconductor' and ticker in SEMICONDUCTOR_SUBCATEGORY:
                category = SEMICONDUCTOR_SUBCATEGORY[ticker]
            else:
                category = old_tag
                
            business_role = get_business_role(category)
            scores = get_exposure_scores(category)
            
            # Company name fallback
            company_name = info.get('shortName') or info.get('longName')
            if not company_name and ticker in BASE_COMPANIES:
                company_name = BASE_COMPANIES[ticker]['company_name']
            if not company_name:
                company_name = ticker
                
            market_cap = info.get('marketCap')
            risk_bucket = get_risk_bucket(market_cap)
            
            avg_volume = info.get('averageVolume', 0)
            price = info.get('currentPrice') or info.get('previousClose', 0)
            liquidity_score = min(10.0, (avg_volume * price) / 1e9) if avg_volume and price else 0.0
            
            rows.append((
                ticker,
                company_name,
                info.get('exchange'),
                info.get('country'),
                info.get('currency'),
                None, # primary_listing
                0, # is_adr
                None, # cik
                None, # isin
                None, # figi
                info.get('sector'),
                info.get('industry'),
                None, None, # gics
                category,
                business_role,
                info.get('longBusinessSummary'),
                None, None, None, # products, markets, themes
                scores['ai'], scores['data_center'], scores['consumer'], scores['automotive'],
                scores['industrial'], scores['china'], scores['memory'], scores['foundry'],
                scores['equipment'], scores['optical'],
                market_cap,
                info.get('sharesOutstanding'),
                info.get('floatShares'),
                avg_volume,
                avg_volume * price if avg_volume and price else None,
                liquidity_score,
                risk_bucket,
                pd.Timestamp.now().isoformat()
            ))
            
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    cur.executemany('''
        INSERT OR REPLACE INTO ticker_master (
            ticker, company_name, exchange, country, currency, primary_listing, is_adr,
            cik, isin, figi, sector, industry, gics_sector, gics_industry,
            semiconductor_category, business_role, company_description, main_products,
            main_end_markets, main_themes, ai_exposure_score, data_center_exposure_score,
            consumer_exposure_score, automotive_exposure_score, industrial_exposure_score,
            china_exposure_score, memory_cycle_exposure_score, foundry_exposure_score,
            equipment_cycle_exposure_score, optical_networking_exposure_score,
            market_cap, shares_outstanding, float_shares, average_daily_volume_20d,
            average_dollar_volume_20d, liquidity_score, risk_bucket, last_updated
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', rows)
    
    conn.commit()
    print(f"Inserted {len(rows)} records into ticker_master")
    conn.close()

if __name__ == '__main__':
    populate_ticker_master()
