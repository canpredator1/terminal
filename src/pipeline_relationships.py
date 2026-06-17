import sqlite3
import pandas as pd
import json
from pathlib import Path

from src.db_schema import DEFAULT_DB_PATH

def populate_relationships():
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cur = conn.cursor()
    
    csv_path = Path('data/output/company_relationships.csv')
    if not csv_path.exists():
        print("company_relationships.csv not found.")
        return
        
    print("Populating relationships...")
    df = pd.read_csv(csv_path)
    
    # Track ticker stats
    stats = {}
    
    rows = []
    for _, row in df.iterrows():
        src = row['source_ticker']
        tgt = row['target_ticker']
        rtype = row['relationship_type']
        
        rid = f"{src}_{tgt}_{rtype}"
        
        if src not in stats: stats[src] = {'up':0, 'down':0, 'cust':0, 'sup':0, 'comp':0, 'theme':0, 'str':[], 'conf':[], 'sources':[], 'targets':[]}
        if tgt not in stats: stats[tgt] = {'up':0, 'down':0, 'cust':0, 'sup':0, 'comp':0, 'theme':0, 'str':[], 'conf':[], 'sources':[], 'targets':[]}
        
        d = row['direction']
        if d == 'upstream':
            stats[src]['up'] += 1
            stats[tgt]['down'] += 1
            if 'supplier' in rtype:
                stats[src]['sup'] += 1
                stats[tgt]['cust'] += 1
        elif d == 'downstream':
            stats[src]['down'] += 1
            stats[tgt]['up'] += 1
            if 'customer' in rtype:
                stats[src]['cust'] += 1
                stats[tgt]['sup'] += 1
        elif d == 'competitor':
            stats[src]['comp'] += 1
            stats[tgt]['comp'] += 1
        else:
            stats[src]['theme'] += 1
            stats[tgt]['theme'] += 1
            
        stats[src]['str'].append(row['strength_score'])
        stats[tgt]['str'].append(row['strength_score'])
        stats[src]['conf'].append(row['confidence_score'])
        stats[tgt]['conf'].append(row['confidence_score'])
        
        stats[tgt]['sources'].append(src)
        stats[src]['targets'].append(tgt)
        
        # Categorize
        cat = rtype
        eff = 'mixed'
        if d == 'upstream': eff = 'positive_correlation'
        elif d == 'downstream': eff = 'positive_correlation'
        elif d == 'competitor': eff = 'negative_correlation'
        
        lmin, lmax = 0, 0
        if d == 'upstream': lmin, lmax = 1, 5
        elif d == 'downstream': lmin, lmax = 1, 5
        elif d == 'competitor': lmin, lmax = 0, 3
        
        rows.append((
            rid, src, tgt, rtype, cat, eff,
            row['strength_score'], row['confidence_score'],
            row['evidence_source'], row.get('source_url'), row.get('evidence_text'),
            1 if row['evidence_source'] == 'sec_filing' else 0,
            None, lmin, lmax, None, None, None, row.get('notes')
        ))
        
    cur.executemany('''
        INSERT OR REPLACE INTO company_relationships (
            relationship_id, source_ticker, target_ticker, relationship_type, relationship_category,
            expected_effect_direction, relationship_strength_score, confidence_score, evidence_source,
            evidence_url, evidence_text, is_verified, source_filing_date, expected_lag_min_days,
            expected_lag_max_days, historical_lag_observed, relationship_start_date, relationship_end_date, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', rows)
    
    prof_rows = []
    for t, s in stats.items():
        from collections import Counter
        top_src = [k for k,v in Counter(s['sources']).most_common(5)]
        top_tgt = [k for k,v in Counter(s['targets']).most_common(5)]
        
        prof_rows.append((
            t, s['up'], s['down'], s['cust'], s['sup'], s['comp'], s['theme'],
            sum(s['str'])/len(s['str']) if s['str'] else 0,
            sum(s['conf'])/len(s['conf']) if s['conf'] else 0,
            json.dumps(top_src), json.dumps(top_tgt),
            None, None, None, None
        ))
        
    cur.executemany('''
        INSERT OR REPLACE INTO ticker_relationship_profile (
            ticker, number_of_upstream_relationships, number_of_downstream_relationships,
            number_of_customer_relationships, number_of_supplier_relationships,
            number_of_competitor_relationships, number_of_theme_relationships,
            average_relationship_strength, average_relationship_confidence,
            top_source_tickers_that_affect_this_ticker, top_target_tickers_this_ticker_affects,
            main_relationship_categories, relationship_dependency_score, theme_dependency_score,
            supplier_customer_dependency_score
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', prof_rows)
    
    conn.commit()
    conn.close()
    print("Done populating relationships.")

if __name__ == '__main__':
    populate_relationships()
