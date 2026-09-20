import os
import pandas as pd
import yfinance as yf
import json

# ---------- YOUR ALPHA VANTAGE API KEY ----------
ALPHA_VANTAGE_KEY = "CRS1NOBNQ87N5YWL"   # <-- already filled for you
# ------------------------------------------------

# ---------- YOUR STOCK LIST ----------
stock_symbols = [
    'NVDA', 'SMCI', 'PLTR', 'NOW', 'ZS', 'CRWD',
     'TTD', 'INTU', 'NBIX', 'SSNC', 'ALAB',
     'AXTI', 'LITE', 'BE', 'TSEM', 'VSXY', 'VICR',
    'META', 'AMZN', 'GOOGL', 'AAPL', 'MSFT', 'TSLA', 'NFLX', 'qqq','spy', 'mu','amzn','spot'
]
# -------------------------------------

stocks_data = []

def fmt(v, d=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return round(float(v), d)
    except (ValueError, TypeError):
        return None

def fmt_mc(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v) / 1e9
    except (ValueError, TypeError):
        return None

for sym in stock_symbols:
    print(f'Processing {sym}...')
    t = yf.Ticker(sym)
    info = t.info
    hist = t.history(period='1y')

    if hist.empty or len(hist) < 2:
        print(f'  SKIP {sym}: no price history')
        continue

    # --- Revenue growth ---
    rev_qoq = None
    rev_yoy = None

    if info.get('revenueGrowth') is not None:
        rev_qoq = info['revenueGrowth']

    quarterly_df = None
    try:
        if hasattr(t, 'quarterly_income_stmt') and t.quarterly_income_stmt is not None:
            quarterly_df = t.quarterly_income_stmt
        elif hasattr(t, 'quarterly_financials') and t.quarterly_financials is not None:
            quarterly_df = t.quarterly_financials
    except Exception:
        pass

    if quarterly_df is not None and not quarterly_df.empty:
        revenue_row = None
        possible_names = ['Total Revenue', 'Revenue', 'TotalRevenue', 'Revenues']
        for name in possible_names:
            if name in quarterly_df.index:
                revenue_row = quarterly_df.loc[name]
                break
        if revenue_row is not None and len(revenue_row) >= 5:
            latest = revenue_row.iloc[0]
            prev = revenue_row.iloc[1] if len(revenue_row) >= 2 else None
            year_ago = revenue_row.iloc[4] if len(revenue_row) >= 5 else None

            if rev_qoq is None and prev is not None and prev != 0:
                rev_qoq = (latest - prev) / prev
            if year_ago is not None and year_ago != 0:
                rev_yoy = (latest - year_ago) / year_ago

    if rev_yoy is None:
        annual_df = None
        try:
            if hasattr(t, 'income_stmt') and t.income_stmt is not None:
                annual_df = t.income_stmt
            elif hasattr(t, 'financials') and t.financials is not None:
                annual_df = t.financials
        except Exception:
            pass
        if annual_df is not None and not annual_df.empty:
            revenue_row = None
            for name in ['Total Revenue', 'Revenue', 'TotalRevenue', 'Revenues']:
                if name in annual_df.index:
                    revenue_row = annual_df.loc[name]
                    break
            if revenue_row is not None and len(revenue_row) >= 2:
                latest = revenue_row.iloc[0]
                prev = revenue_row.iloc[1]
                if prev != 0:
                    rev_yoy = (latest - prev) / prev

    # --- Other data ---
    price = info.get('currentPrice')
    mc = info.get('marketCap')
    industry = info.get('industry', 'N/A')

    # --- Historical prices for dynamic calculation ---
    close_prices = hist['Close']
    price_1y_ago = close_prices.iloc[0] if len(close_prices) >= 252 else close_prices.iloc[0]
    price_1m_ago = close_prices.iloc[-22] if len(close_prices) >= 22 else close_prices.iloc[0]
    close_prev = close_prices.iloc[-2] if len(close_prices) >= 2 else close_prices.iloc[-1]

    price_chg_today = (price - close_prev) / close_prev * 100 if price else None

    stocks_data.append({
        'symbol': sym,
        'industry': industry,
        'market_cap_bn': fmt_mc(mc),
        'rev_qoq_pct': fmt(rev_qoq * 100 if rev_qoq is not None else None, 1),
        'rev_yoy_pct': fmt(rev_yoy * 100 if rev_yoy is not None else None, 1),
        'price': fmt(price, 2),
        'price_1y_ago': fmt(price_1y_ago, 2),
        'price_1m_ago': fmt(price_1m_ago, 2),
        'chg_today_pct': fmt(price_chg_today, 1),
    })
    print(f'  {sym}: OK')

if not stocks_data:
    print('No stocks data collected.')
    exit()

# Sort by YoY revenue growth
stocks_data.sort(key=lambda x: x['rev_yoy_pct'] if x['rev_yoy_pct'] is not None else -999, reverse=True)

# -------------------- BUILD HTML WITH EMBEDDED DATA --------------------
html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Top Stocks Report — Live Data</title>
<link rel="stylesheet" href="https://cdn.datatables.net/1.10.20/css/jquery.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.3.1.js"></script>
<script src="https://cdn.datatables.net/1.10.20/js/jquery.dataTables.min.js"></script>
<style>
  :root {{
    --bg: #0f1119;
    --surface: #1a1d2e;
    --surface2: #232740;
    --border: #3a4060;
    --text: #f0f2fa;
    --muted: #c8ccdb;
    --accent: #00d4aa;
    --gold: #f5c842;
    --yellow: #ffd966;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 30px 20px;
  }}
  .header {{
    width: 100%;
    max-width: 1200px;
    margin-bottom: 28px;
    text-align: center;
  }}
  .header h1 {{
    font-size: 2rem;
    font-weight: 700;
    margin: 0 0 6px;
    color: #f5c842;
  }}
  .header .sub {{ color: #ffffff; font-size: 0.95rem; margin: 0; }}
  .header .meta {{
    display: flex;
    justify-content: center;
    gap: 24px;
    margin-top: 14px;
    font-size: 0.82rem;
    color: var(--yellow);
  }}
  .header .meta a {{
    background: var(--surface);
    padding: 5px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    color: var(--yellow);
    text-decoration: none;
    transition: all 0.15s;
  }}
  .header .meta a:hover {{
    background: var(--surface2);
    border-color: var(--accent);
    transform: scale(1.03);
  }}
  .controls {{
    width: 100%;
    max-width: 1200px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .controls .legend a {{
    color: #ffffff;
    background: var(--surface);
    padding: 7px 16px;
    border-radius: 20px;
    border: 1px solid var(--border);
    text-decoration: none;
    font-weight: 700;
    transition: all 0.15s;
  }}
  .controls .legend a:hover {{
    background: var(--surface2);
    border-color: var(--accent);
    transform: scale(1.03);
  }}
  #stocksTable_wrapper {{
    width: 100%;
    max-width: 1200px;
    background: var(--surface);
    border-radius: 12px;
    border: 1px solid var(--border);
    overflow: hidden;
    box-shadow: 0 4px 30px rgba(0,0,0,0.4);
  }}
  #stocksTable thead th {{
    background: var(--surface2);
    color: var(--text);
    font-weight: 600;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    padding: 12px 10px;
    border-bottom: 2px solid var(--border);
    text-align: center;
    white-space: nowrap;
  }}
  #stocksTable tbody td {{
    padding: 10px 10px;
    text-align: center;
    font-size: 0.88rem;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }}
  #stocksTable tbody tr:hover {{ background: var(--surface2); }}
  #stocksTable tbody td:first-child {{ font-weight: 700; color: var(--gold); font-size: 0.95rem; }}
  #stocksTable tbody td:nth-child(2) {{ color: var(--yellow); font-size: 0.8rem; }}
  #stocksTable tbody td:nth-child(4) {{ font-family: monospace; font-weight: 600; color: var(--gold); }}
  .dataTables_length, .dataTables_filter, .dataTables_info, .dataTables_paginate {{
    color: var(--muted);
    font-size: 0.8rem;
    padding: 10px 14px;
    background: var(--surface);
    border-top: 1px solid var(--border);
  }}
  .dataTables_filter input {{
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 4px 8px;
    border-radius: 4px;
    font-family: inherit;
    font-size: 0.8rem;
    width: 180px;
  }}
  .footer-note {{ margin-top: 24px; color: var(--muted); font-size: 0.8rem; text-align: center; max-width: 800px; }}
  .footer-note a {{ color: var(--accent); }}
  .live-badge {{ font-size: 0.7rem; background: #00d4aa20; padding: 2px 10px; border-radius: 20px; color: var(--accent); border: 1px solid var(--accent); }}
</style>
<script>
// ------- EMBEDDED FUNDAMENTALS & HISTORICAL PRICES (generated by Python) -------
const STOCKS_DATA = {json.dumps(stocks_data, indent=2)};

// ------- YOUR ALPHA VANTAGE API KEY -------
const ALPHA_VANTAGE_KEY = "{ALPHA_VANTAGE_KEY}";
// ---------------------------------------------

// ------- FETCH LIVE PRICES & RENDER TABLE -------
$(document).ready(function() {{
    const symbols = STOCKS_DATA.map(s => s.symbol).join(',');

    // 1. Fetch live quotes from Alpha Vantage
    $.ajax({{
        url: `https://www.alphavantage.co/query?function=BATCH_STOCK_QUOTES&symbols=${{symbols}}&apikey=${{CRS1NOBNQ87N5YWL}}`,
        method: 'GET',
        dataType: 'json',
        timeout: 10000
    }})
    .done(function(response) {{
        const quotes = response['Stock Quotes'] || [];
        const quoteMap = {{}};
        quotes.forEach(q => {{
            const sym = q['1. symbol'];
            const price = parseFloat(q['2. price']);
            const changePct = parseFloat(q['4. changePercent'].replace('%',''));
            quoteMap[sym] = {{ price, changePct }};
        }});

        // 2. Merge live data with fundamentals and calculate YoY / MoM
        const tableData = STOCKS_DATA.map(item => {{
            const live = quoteMap[item.symbol] || {{}};
            const price = live.price !== undefined ? live.price : item.price;
            const chgToday = live.changePct !== undefined ? live.changePct : item.chg_today_pct;
            const priceYoY = item.price_1y_ago ? ((price - item.price_1y_ago) / item.price_1y_ago * 100) : null;
            const priceMoM = item.price_1m_ago ? ((price - item.price_1m_ago) / item.price_1m_ago * 100) : null;

            return {{
                ...item,
                price: price,
                chg_today_pct: chgToday,
                price_yoy_pct: priceYoY,
                price_mom_pct: priceMoM,
                hasLive: live.price !== undefined
            }};
        }});

        // 3. Render table
        let html = '';
        tableData.forEach(r => {{
            const liveIndicator = r.hasLive ? '' : ' (cached)';
            html += `<tr>
                <td><a href="https://finance.yahoo.com/quote/${{r.symbol}}" target="_blank" style="color:var(--gold);font-weight:700;text-decoration:none;">${{r.symbol}}</a> <a href="https://www.tradingview.com/symbols/${{r.symbol}}/" target="_blank" title="Chart" style="text-decoration:none;">📈</a></td>
                <td>${{r.industry}}</td>
                <td>${{r.chg_today_pct !== null ? r.chg_today_pct.toFixed(1) : 'N/A'}}</td>
                <td>${{r.market_cap_bn !== null ? r.market_cap_bn.toFixed(1) + 'B' : 'N/A'}}</td>
                <td>${{r.rev_qoq_pct !== null ? r.rev_qoq_pct.toFixed(1) : 'N/A'}}</td>
                <td>${{r.rev_yoy_pct !== null ? r.rev_yoy_pct.toFixed(1) : 'N/A'}}</td>
                <td>${{r.price !== null ? r.price.toFixed(2) : 'N/A'}}${{liveIndicator}}</td>
                <td>${{r.price_yoy_pct !== null ? r.price_yoy_pct.toFixed(1) : 'N/A'}}</td>
                <td>${{r.price_mom_pct !== null ? r.price_mom_pct.toFixed(1) : 'N/A'}}</td>
            </tr>`;
        }});

        $('#stocksTable tbody').html(html);

        // 4. Re-initialize DataTable
        if ($.fn.DataTable.isDataTable('#stocksTable')) {{
            $('#stocksTable').DataTable().destroy();
        }}
        $('#stocksTable').DataTable({{
            pageLength: 20,
            lengthMenu: [[10, 20, 50, -1], [10, 20, 50, "All"]],
            order: [[5, "desc"]],
            columnDefs: [
                {{ targets: 3, type: 'num', render: (data, type) => {{
                    if (type === 'sort' || type === 'filter') {{
                        let n = parseFloat(String(data).replace('B','').replace('N/A',''));
                        return isNaN(n) ? null : n;
                    }}
                    return data;
                }}}},
                {{ targets: [2,4,5,7,8], type: 'num', render: (data, type) => {{
                    if (type === 'sort' || type === 'filter') {{
                        let n = parseFloat(String(data).replace('N/A',''));
                        return isNaN(n) ? null : n;
                    }}
                    return data;
                }}}}
            ]
        }});

        // 5. Show timestamp
        const now = new Date();
        $('#updateTime').text(`Data live as of ${{now.toLocaleString()}}`);
    }})
    .fail(function(err) {{
        // Fallback: render with static data only
        console.warn('Alpha Vantage fetch failed, using cached prices.', err);
        let html = '';
        STOCKS_DATA.forEach(r => {{
            html += `<tr>
                <td><a href="https://finance.yahoo.com/quote/${{r.symbol}}" target="_blank" style="color:var(--gold);font-weight:700;text-decoration:none;">${{r.symbol}}</a> <a href="https://www.tradingview.com/symbols/${{r.symbol}}/" target="_blank" title="Chart" style="text-decoration:none;">📈</a></td>
                <td>${{r.industry}}</td>
                <td>${{r.chg_today_pct !== null ? r.chg_today_pct.toFixed(1) : 'N/A'}}</td>
                <td>${{r.market_cap_bn !== null ? r.market_cap_bn.toFixed(1) + 'B' : 'N/A'}}</td>
                <td>${{r.rev_qoq_pct !== null ? r.rev_qoq_pct.toFixed(1) : 'N/A'}}</td>
                <td>${{r.rev_yoy_pct !== null ? r.rev_yoy_pct.toFixed(1) : 'N/A'}}</td>
                <td>${{r.price !== null ? r.price.toFixed(2) : 'N/A'}} (cached)</td>
                <td>N/A</td>
                <td>N/A</td>
            </tr>`;
        }});
        $('#stocksTable tbody').html(html);
        if ($.fn.DataTable.isDataTable('#stocksTable')) {{
            $('#stocksTable').DataTable().destroy();
        }}
        $('#stocksTable').DataTable({{
            pageLength: 20,
            lengthMenu: [[10, 20, 50, -1], [10, 20, 50, "All"]],
            order: [[5, "desc"]],
            columnDefs: [
                {{ targets: 3, type: 'num', render: (data, type) => {{
                    if (type === 'sort' || type === 'filter') {{
                        let n = parseFloat(String(data).replace('B','').replace('N/A',''));
                        return isNaN(n) ? null : n;
                    }}
                    return data;
                }}}},
                {{ targets: [2,4,5,7,8], type: 'num', render: (data, type) => {{
                    if (type === 'sort' || type === 'filter') {{
                        let n = parseFloat(String(data).replace('N/A',''));
                        return isNaN(n) ? null : n;
                    }}
                    return data;
                }}}}
            ]
        }});
        $('#updateTime').text('Data cached (API unavailable)');
    }});
}});
</script>
</head>
<body>

<div class="header">
  <h1>Top Stocks Report — Revenue Growth Leaders</h1>
  <p class="sub">Live prices from Alpha Vantage • Sorted by YoY Revenue Growth</p>
  <div class="meta">
    <a href="https://www.google.com/search?q=FASTEST+GROWING+STOCKS" target="_blank">🔍 Google Search Growth</a>
    <a href="https://finviz.com/screener" target="_blank">📊 Finviz Screener</a>
    <span class="live-badge">⚡ LIVE PRICES</span>
  </div>
</div>

<div class="controls">
  <div class="legend">
    <a href="how-to-customize.html">Change Symbols -Link</a>
  </div>
  <div style="font-size:0.8rem;color:var(--muted);">Not financial advice — do your own research</div>
</div>

<div id="stocksTable_wrapper">
<table id="stocksTable" class="display">
<thead>
  <tr>
    <th>Symbol</th>
    <th>Industry</th>
    <th>Today's %</th>
    <th>Market Cap</th>
    <th>Rev QoQ %</th>
    <th>Rev YoY %</th>
    <th>Price</th>
    <th>Price Δ YoY %</th>
    <th>Price Δ MoM %</th>
  </tr>
</thead>
<tbody>
  <!-- Filled dynamically -->
</tbody>
</table>
</div>

<p class="footer-note" id="updateTime">Loading live prices...</p>

<p class="footer-note">
  Data sourced from <a href="https://finance.yahoo.com" target="_blank">Yahoo Finance</a> (fundamentals) &amp; <a href="https://www.alphavantage.co" target="_blank">Alpha Vantage</a> (live prices).<br/>
  Refresh this page to get the latest prices — no re‑upload needed!<br/>
  Contact: JLITZ100@GMAIL.COM
</p>

</body>
</html>'''

# -------------------- SAVE TO YOUR FOLDER --------------------
output_dir = r'C:\Users\jlitw\Desktop\GROWTH STOCKS'
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'index.html')

with open(output_path, 'w') as f:
    f.write(html)

print(f'\n✅ New dynamic index.html saved to {output_path}')
print(f'   {len(stocks_data)} stocks included.')
print('   Upload this file to Netlify — it will now fetch live prices on every browser refresh.')