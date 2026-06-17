import sqlite3
import json
import pandas as pd
from pathlib import Path
import re

from src.db_schema import DEFAULT_DB_PATH

def generate_enhanced_map():
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 1. Fetch nodes
    df_nodes = pd.read_sql_query('''
        SELECT ticker as id, ticker as label, company_name as company, 
               semiconductor_category as tag, market_cap, liquidity_score, ai_overview
        FROM ticker_master
    ''', conn)
    
    # 2. Fetch edges
    df_edges = pd.read_sql_query('''
        SELECT source_ticker as "from", target_ticker as "to", 
               relationship_type as type, 
               CASE 
                   WHEN relationship_type LIKE '%supplier%' THEN 'upstream'
                   WHEN relationship_type LIKE '%customer%' THEN 'downstream'
                   WHEN relationship_type LIKE '%partner%' THEN 'lateral'
                   WHEN relationship_type = 'competitor' THEN 'competitor'
                   ELSE 'lateral'
               END as direction,
               relationship_strength_score as strength,
               confidence_score as confidence, evidence_source as evidence
        FROM company_relationships
        WHERE is_verified = 1 OR evidence_source = 'manual_seed'
    ''', conn)
    
    # Calculate connection counts per node
    conn_counts = {}
    for _, row in df_edges.iterrows():
        conn_counts[row['from']] = conn_counts.get(row['from'], 0) + 1
        conn_counts[row['to']] = conn_counts.get(row['to'], 0) + 1
        
    df_nodes['connections'] = df_nodes['id'].map(lambda x: conn_counts.get(x, 0))
    df_nodes = df_nodes[df_nodes['connections'] > 0]
    
    # 3. Fetch ALL details
    details_dict = {}
    
    df_exposures = pd.read_sql_query('SELECT * FROM ticker_master', conn)
    
    latest_market_date = pd.read_sql_query('SELECT MAX(date) FROM ticker_daily_market_state', conn).iloc[0,0]
    df_market = pd.DataFrame()
    if latest_market_date:
        df_market = pd.read_sql_query(f"SELECT * FROM ticker_daily_market_state WHERE date = '{latest_market_date}'", conn)
        
    df_earnings = pd.read_sql_query('SELECT * FROM ticker_earnings_profile', conn)
    
    # Get latest fundamentals date for each ticker
    df_fund = pd.read_sql_query('''
        SELECT f.* FROM fundamentals_quarterly f
        INNER JOIN (SELECT ticker, MAX(period_end_date) as latest FROM fundamentals_quarterly GROUP BY ticker) m
        ON f.ticker = m.ticker AND f.period_end_date = m.latest
    ''', conn)
    
    df_val = pd.read_sql_query('SELECT * FROM valuation_snapshot', conn)
    
    latest_sent_date = pd.read_sql_query('SELECT MAX(date) FROM sentiment_daily', conn).iloc[0,0]
    df_sent = pd.DataFrame()
    if latest_sent_date:
        df_sent = pd.read_sql_query(f"SELECT * FROM sentiment_daily WHERE date = '{latest_sent_date}'", conn)
        
    df_news = pd.read_sql_query('SELECT * FROM news_events', conn)
    
    for ticker in df_nodes['id']:
        d = {}
        exps = df_exposures[df_exposures['ticker'] == ticker]
        if not exps.empty: d['master'] = exps.iloc[0].dropna().to_dict()
            
        if not df_market.empty:
            mkt = df_market[df_market['ticker'] == ticker]
            if not mkt.empty: d['market'] = mkt.iloc[0].dropna().to_dict()
                
        ern = df_earnings[df_earnings['ticker'] == ticker]
        if not ern.empty: d['earnings'] = ern.iloc[0].dropna().to_dict()
            
        fnd = df_fund[df_fund['ticker'] == ticker]
        if not fnd.empty: d['fundamentals'] = fnd.iloc[0].dropna().to_dict()
            
        val = df_val[df_val['ticker'] == ticker]
        if not val.empty: d['valuation'] = val.iloc[0].dropna().to_dict()
            
        if not df_sent.empty:
            snt = df_sent[df_sent['ticker'] == ticker]
            if not snt.empty: d['sentiment'] = snt.iloc[0].dropna().to_dict()
                
        news = df_news[df_news['ticker'] == ticker]
        if not news.empty:
            d['news'] = news[['headline', 'url', 'source', 'published_at']].head(10).to_dict('records')
            
        details_dict[ticker] = d

    conn.close()

    graphData = {
        "nodes": df_nodes.to_dict('records'),
        "edges": df_edges.to_dict('records'),
        "details": details_dict
    }

    orig_html_path = Path('data/output/relationship_map.html')
    with open(orig_html_path, 'r') as f:
        html = f.read()
        
    # Fix D3 Lag: Increase alphaDecay so physics settle fast, and disable tick rendering when mostly stopped
    html = html.replace('.alphaDecay(0.015);', '.alphaDecay(0.05);')
    
    # UI Injection
    css_addition = """
  /* --- Side Panel --- */
  .side-panel {
    position: fixed;
    top: 56px; right: -450px; bottom: 0;
    width: 450px;
    background: rgba(12, 16, 30, 0.98);
    backdrop-filter: blur(20px);
    border-left: 1px solid rgba(255,255,255,0.1);
    box-shadow: -10px 0 30px rgba(0,0,0,0.8);
    z-index: 150;
    transition: right 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .side-panel.open { right: 0; }
  .sp-header {
    padding: 20px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    background: rgba(12, 16, 30, 1);
    position: relative;
    z-index: 10;
  }
  .sp-close {
    position: absolute;
    top: 20px; right: 20px;
    background: transparent;
    border: none;
    color: #64748b;
    font-size: 20px;
    cursor: pointer;
  }
  .sp-close:hover { color: #e0e6f0; }
  .sp-ticker { font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 4px; }
  .sp-company { font-size: 14px; color: #94a3b8; margin-bottom: 12px; }
  .sp-tag {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 6px;
  }
  .sp-content {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
  }
  .sp-section {
    margin-bottom: 24px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px;
    padding: 16px;
  }
  .sp-section h3 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #64748b;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .sp-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .sp-metric {
    display: flex;
    flex-direction: column;
    gap: 4px;
    border-bottom: 1px solid rgba(255,255,255,0.02);
    padding-bottom: 4px;
  }
  .sp-m-label { font-size: 10px; color: #64748b; text-transform: capitalize; }
  .sp-m-value { font-size: 12px; font-weight: 500; color: #e0e6f0; word-break: break-word; }
  .sp-m-value.pos { color: #10b981; }
  .sp-m-value.neg { color: #ef4444; }
  
  .sp-news-item {
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.02);
  }
  .sp-news-item a { color: #60a5fa; text-decoration: none; font-size: 12px; font-weight: 500; display: block; margin-bottom: 4px; }
  .sp-news-item a:hover { text-decoration: underline; }
  .sp-news-meta { font-size: 10px; color: #64748b; }
  
  #radar-chart { width: 100%; height: 260px; margin-top: 10px; }
"""
    
    html = html.replace('</style>', css_addition + '\n</style>')
    
    html_addition = """
<div class="side-panel" id="side-panel">
  <div class="sp-header">
    <button class="sp-close" id="sp-close">×</button>
    <div class="sp-ticker" id="sp-ticker">TICKER</div>
    <div class="sp-company" id="sp-company">Company Name</div>
    <div class="sp-tag" id="sp-tag">Category</div>
  </div>
  <div class="sp-content" id="sp-content">
    <!-- Dynamic content goes here -->
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
"""
    
    html = html.replace('<div class="tooltip" id="tooltip"></div>', '<div class="tooltip" id="tooltip"></div>\n' + html_addition)
    
    pattern = re.compile(r'graphData = \{.*?\};', re.DOTALL)
    json_data = json.dumps(graphData)
    html = pattern.sub(lambda m: f'graphData = {json_data};', html)
    
    js_addition = """
  const sidePanel = document.getElementById('side-panel');
  document.getElementById('sp-close').onclick = () => {
    sidePanel.classList.remove('open');
    clickedNode = null;
    updateHighlight();
  };
  
  let radarChart = null;

  function generateGridHTML(dataObj, skipKeys=[], skipZeroes=false) {
    let html = '<div class="sp-grid">';
    for (const [key, val] of Object.entries(dataObj)) {
      if (skipKeys.includes(key) || val === null || val === '') continue;
      if (skipZeroes && val === 0 && key !== 'general_sentiment_score') continue;
      
      let fmtVal = val;
      if (typeof val === 'number') {
        if (Math.abs(val) > 1e9) fmtVal = (val/1e9).toFixed(2) + 'B';
        else if (Math.abs(val) > 1e6) fmtVal = (val/1e6).toFixed(2) + 'M';
        else if (val % 1 !== 0) fmtVal = val.toFixed(4);
      }
      
      let label = key.replace(/_/g, ' ');
      html += `<div class="sp-metric"><span class="sp-m-label">${label}</span><span class="sp-m-value">${fmtVal}</span></div>`;
    }
    html += '</div>';
    return html;
  }

  function openSidePanel(d) {
    try {
      console.log("Opening side panel for:", d.id);
      if (!sidePanel) {
        alert("CRITICAL ERROR: sidePanel DOM element not found!");
        return;
      }
      sidePanel.classList.add('open');
      
      const elTicker = document.getElementById('sp-ticker');
      if (elTicker) elTicker.textContent = d.id || 'Unknown';
      
      const elCompany = document.getElementById('sp-company');
      if (elCompany) elCompany.textContent = d.company || 'Unknown';
      
      const tagEl = document.getElementById('sp-tag');
      if (tagEl) {
        tagEl.textContent = TAG_LABELS[d.tag] || d.tag || 'Unknown';
        tagEl.style.background = (TAG_COLORS[d.tag] || '#64748b') + '22';
        tagEl.style.color = TAG_COLORS[d.tag] || '#64748b';
      }
      
      const details = graphData.details[d.id] || {};
      let contentHtml = '';
      
      if (d.ai_overview) {
        contentHtml += `
          <div class="sp-section" style="background: rgba(124, 58, 237, 0.05); border: 1px solid rgba(124, 58, 237, 0.2);">
            <h3 style="color: #c4b5fd;">✨ AI Overview</h3>
            <div style="font-size: 13px; color: #e2e8f0; line-height: 1.6; white-space: pre-wrap;">${d.ai_overview}</div>
          </div>
        `;
      }
      
      if (details.market) {
        contentHtml += `<div class="sp-section"><h3>📈 Market Status</h3>`;
        contentHtml += generateGridHTML(details.market, ['ticker', 'date']);
        contentHtml += `</div>`;
      }
      
      if (details.earnings) {
        contentHtml += `<div class="sp-section"><h3>💰 Earnings Profile</h3>`;
        contentHtml += generateGridHTML(details.earnings, ['ticker', 'last_updated']);
        contentHtml += `</div>`;
      }
      
      if (details.fundamentals) {
        contentHtml += `<div class="sp-section"><h3>🏢 Fundamentals</h3>`;
        contentHtml += generateGridHTML(details.fundamentals, ['ticker', 'quarter']);
        contentHtml += `</div>`;
      }
      
      if (details.valuation) {
        contentHtml += `<div class="sp-section"><h3>⚖️ Valuation</h3>`;
        contentHtml += generateGridHTML(details.valuation, ['ticker', 'date']);
        contentHtml += `</div>`;
      }
      
      if (details.sentiment) {
        contentHtml += `<div class="sp-section"><h3>📰 News Sentiment & Context</h3>`;
        contentHtml += generateGridHTML(details.sentiment, ['ticker', 'date'], true);
        
        if (details.news && details.news.length > 0) {
          contentHtml += `<div style="margin-top: 16px;">`;
          details.news.forEach(n => {
            const dateStr = n.published_at ? n.published_at.substring(0, 10) : 'Unknown Date';
            const url = n.url || '#';
            const headline = n.headline || n.title || 'News Update';
            const source = n.source || 'Yahoo Finance';
            contentHtml += `
              <div class="sp-news-item">
                <a href="${url}" target="_blank">${headline}</a>
                <div class="sp-news-meta">${source} • ${dateStr}</div>
              </div>
            `;
          });
          contentHtml += `</div>`;
        }
        contentHtml += `</div>`;
      }
      
      if (details.master) {
        contentHtml += `<div class="sp-section"><h3>📊 Thematic Exposures</h3>
          <div style="position: relative; height: 260px; width: 100%;">
            <canvas id="radar-chart"></canvas>
          </div>
        </div>`;
      }

      // Powered By Footer
      contentHtml += `
        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
          <span style="font-size: 10px; font-weight: 600; color: #64748b; letter-spacing: 0.5px; text-transform: uppercase;">
            Powered by <span style="color: #7c3aed;">Yahoo Scout</span>
          </span>
        </div>
      `;

      const spContent = document.getElementById('sp-content');
      if (spContent) {
        spContent.innerHTML = contentHtml;
      } else {
        alert("CRITICAL ERROR: sp-content DOM element not found!");
      }
      
      if (details.master) {
        const exp = details.master;
        const labels = ['AI', 'Data Center', 'Consumer', 'Automotive', 'Industrial', 'China', 'Memory', 'Foundry', 'Equipment', 'Optical'];
        const data = [
          exp.ai_exposure_score||0, exp.data_center_exposure_score||0, exp.consumer_exposure_score||0, 
          exp.automotive_exposure_score||0, exp.industrial_exposure_score||0, exp.china_exposure_score||0, 
          exp.memory_cycle_exposure_score||0, exp.foundry_exposure_score||0, exp.equipment_cycle_exposure_score||0,
          exp.optical_networking_exposure_score||0
        ];
        
        const canvasEl = document.getElementById('radar-chart');
        if (canvasEl) {
          const ctx = canvasEl.getContext('2d');
          if (radarChart) {
             try { radarChart.destroy(); } catch(e) {}
          }
          if (typeof Chart !== 'undefined') {
            radarChart = new Chart(ctx, {
              type: 'radar',
              data: {
                labels: labels,
                datasets: [{
                  label: 'Exposure Score',
                  data: data,
                  backgroundColor: 'rgba(56, 189, 248, 0.2)',
                  borderColor: 'rgba(56, 189, 248, 1)',
                  pointBackgroundColor: 'rgba(56, 189, 248, 1)',
                  pointBorderColor: '#fff',
                  pointHoverBackgroundColor: '#fff',
                  pointHoverBorderColor: 'rgba(56, 189, 248, 1)'
                }]
              },
              options: {
                scales: {
                  r: {
                    angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    pointLabels: { color: '#94a3b8', font: { size: 10 } },
                    ticks: { display: false, min: 0, max: 1 }
                  }
                },
                plugins: { legend: { display: false } },
                maintainAspectRatio: false
              }
            });
          } else {
            console.warn("Chart.js is not loaded.");
          }
        }
      }
    } catch (err) {
      alert("Side Panel Error: " + err.message);
      console.error(err);
    }
  }
"""
    
    click_pattern = re.compile(r'clickedNode = clickedNode === d\.id \? null : d\.id;\n\s*updateHighlight\(\);', re.MULTILINE)
    replacement = """clickedNode = clickedNode === d.id ? null : d.id;
    updateHighlight();
    if (clickedNode) openSidePanel(d); else sidePanel.classList.remove('open');"""
    html = click_pattern.sub(replacement, html)
    
    html = html.replace('</script>\n</body>', js_addition + '\n</script>\n</body>')
    
    output_path = Path('data/output/relationship_map_v4.html')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
        
    print(f"Enhanced map saved to {output_path}")

if __name__ == "__main__":
    generate_enhanced_map()
