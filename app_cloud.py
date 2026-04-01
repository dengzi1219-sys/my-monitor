import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
import os
import json
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor

# --- 1. 核心环境适配 ---
is_local = any(os.path.exists(p) for p in ["D:\\vscode", "D:\\code", "D:\\cloud"])
if is_local:
    os.environ['HTTP_PROXY'] = "http://127.0.0.1:7892"
    os.environ['HTTPS_PROXY'] = "http://127.0.0.1:7892"
else:
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)

DB_FILE = "stocks.json"
st.set_page_config(page_title="全球战略情报终端 v12.1_Pro", layout="wide")

# --- 2. 视觉样式 ---
st.markdown("""
    <style>
    .metric-card { border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 12px; margin-bottom: 5px; min-height: 110px; }
    .rec-buy { color: #ff4b4b; font-weight: bold; background: rgba(255, 75, 75, 0.1); padding: 5px 10px; border-radius: 4px; border: 1px solid #ff4b4b; }
    .rec-sell { color: #00eb93; font-weight: bold; background: rgba(0, 235, 147, 0.1); padding: 5px 10px; border-radius: 4px; border: 1px solid #00eb93; }
    .rec-hold { color: #ffa500; font-weight: bold; background: rgba(255, 165, 0, 0.1); padding: 5px 10px; border-radius: 4px; border: 1px solid #ffa500; }
    .news-tag { font-size: 0.7em; padding: 2px 6px; border-radius: 10px; margin-right: 5px; color: white; }
    .tag-finance { background-color: #4a90e2; }
    .tag-world { background-color: #e2a14a; }
    .tag-iran { background-color: #d0021b; }
    .guba-post { font-size: 0.9em; padding: 5px 0; border-bottom: 1px dashed rgba(128,128,128,0.2); }
    .guba-post a { color: #dcdcdc; text-decoration: none; transition: 0.3s; }
    .guba-post a:hover { color: #ff4b4b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心功能 ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_weather(city_en, city_zh):
    try:
        res = requests.get(f"https://wttr.in/{city_en}?format=3&m", timeout=8)
        res.encoding = 'utf-8'
        return res.text.replace(city_en, city_zh).strip() if res.status_code == 200 else f"{city_zh}：同步中"
    except: return f"{city_zh}：信号弱"

@st.cache_data(ttl=300, show_spinner=False)
def get_guba_posts(ticker):
    code = ''.join(filter(str.isdigit, ticker))
    if len(code) != 6: return []
    try:
        url = f"https://guba.eastmoney.com/list,{code}.html"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        posts = []
        for a in soup.find_all('a'):
            href = a.get('href', '')
            title = a.get('title') or a.text.strip()
            if '/news,' in href and title and len(title) > 5 and '$' not in title:
                link = href if href.startswith("http") else "https://guba.eastmoney.com" + href
                if title not in [p['t'] for p in posts]: posts.append({"t": title, "l": link})
            if len(posts) >= 6: break
        return posts
    except: return []

@st.cache_data(ttl=60, show_spinner=False)
def get_intraday_data(ticker):
    try:
        clean_t = str(ticker).upper().replace('.SS', '').replace('.SZ', '')
        is_cn = clean_t.isdigit() and len(clean_t) == 6
        if is_cn:
            market = "1." if clean_t.startswith(('6', '5', '9')) else "0."
            url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={market}{clean_t}&fields1=f1,f2,f3&fields2=f51,f53,f58"
            r = requests.get(url, timeout=5, proxies={"http": None, "https": None}).json()
            if r.get('data') and r['data'].get('trends'):
                df = pd.DataFrame([t.split(',') for t in r['data']['trends']], columns=['Time', 'Price', 'AvgPrice'])
                df['Price'] = df['Price'].astype(float)
                return df
        else:
            y_ticker = f"{clean_t}.SS" if (is_cn and clean_t.startswith(('6', '5', '9'))) else f"{clean_t}.SZ" if is_cn else ticker
            df = yf.Ticker(y_ticker).history(period="1d", interval="1m")
            if not df.empty:
                return df[['Close']].reset_index().rename(columns={'Datetime':'Time', 'Close':'Price'})
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=60, show_spinner=False)
def get_5d_data(ticker):
    try:
        clean_t = str(ticker).upper().replace('.SS', '').replace('.SZ', '')
        is_cn = clean_t.isdigit() and len(clean_t) == 6
        if is_cn:
            market = "1." if clean_t.startswith(('6', '5', '9')) else "0."
            url = f"https://push2.eastmoney.com/api/qt/stock/trends2/get?secid={market}{clean_t}&fields1=f1,f2,f3&fields2=f51,f53,f58&iscr=0&ndays=5"
            r = requests.get(url, timeout=5, proxies={"http": None, "https": None}).json()
            if r.get('data') and r['data'].get('trends'):
                df = pd.DataFrame([t.split(',') for t in r['data']['trends']], columns=['Time', 'Price', 'AvgPrice'])
                df['Price'] = df['Price'].astype(float)
                return df
        else:
            y_ticker = f"{clean_t}.SS" if (is_cn and clean_t.startswith(('6', '5', '9'))) else f"{clean_t}.SZ" if is_cn else ticker
            df = yf.Ticker(y_ticker).history(period="5d", interval="15m")
            if not df.empty:
                return df[['Close']].reset_index().rename(columns={'Datetime':'Time', 'Close':'Price'})
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(ticker):
    df = pd.DataFrame()
    info = {}
    try:
        clean_t = str(ticker).upper().replace('.SS', '').replace('.SZ', '')
        is_cn = clean_t.isdigit() and len(clean_t) == 6
        
        if is_cn:
            market = "1." if clean_t.startswith(('6', '5', '9')) else "0."
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://quote.eastmoney.com/'}
            for f_mode in ["1", "0"]:
                # 🟢 修改：将数据拉取长度放大至 10000 天 (约40年)，满足“建立以来的周K”计算需求
                url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={market}{clean_t}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt={f_mode}&end=20500101&lmt=10000"
                try:
                    r = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=3).json()
                    d = r.get('data')
                    if d and d.get('klines'):
                        info['shortName'] = d.get('name', clean_t)
                        klines = [k.split(',') for k in d['klines']]
                        df = pd.DataFrame(klines, columns=['Date', 'Open', 'Close', 'High', 'Low', 'Volume'])
                        df['Date'] = pd.to_datetime(df['Date'])
                        df.set_index('Date', inplace=True)
                        df = df.astype(float)
                        break
                except: continue

            if df.empty:
                sina_sym = f"sh{clean_t}" if clean_t.startswith(('6', '5', '9')) else f"sz{clean_t}"
                # 🟢 修改：新浪专线同样放大到 10000 天
                sina_url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sina_sym}&scale=240&ma=no&datalen=10000"
                try:
                    res = requests.get(sina_url, proxies={"http": None, "https": None}, timeout=4).json()
                    if res and len(res) > 0:
                        df = pd.DataFrame(res)
                        df.rename(columns={'day':'Date', 'open':'Open', 'close':'Close', 'high':'High', 'low':'Low', 'volume':'Volume'}, inplace=True)
                        df['Date'] = pd.to_datetime(df['Date'])
                        df.set_index('Date', inplace=True)
                        df = df.astype(float)
                        try:
                            r_name = requests.get(f"https://hq.sinajs.cn/list={sina_sym}", headers={'Referer': 'https://finance.sina.com.cn/'}, timeout=2)
                            r_name.encoding = 'gbk'
                            name_str = r_name.text.split('="')[1].split(',')[0]
                            info['shortName'] = name_str if name_str else clean_t
                        except: info['shortName'] = clean_t
                except: pass

        if df.empty:
            y_ticker = f"{clean_t}.SS" if (is_cn and clean_t.startswith(('6', '5', '9'))) else f"{clean_t}.SZ" if is_cn else ticker
            try:
                t_obj = yf.Ticker(y_ticker)
                # 🟢 修改：雅虎也拉取 max 数据
                df = t_obj.history(period="max")
                info = t_obj.info
            except: pass

        if not df.empty and len(df) >= 2:
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            diff = df['Close'].diff()
            up, down = diff.copy(), diff.copy()
            up[up < 0] = 0; down[down > 0] = 0
            roll_up = up.rolling(14).mean(); roll_down = down.abs().rolling(14).mean()
            df['RSI'] = 100.0 - (100.0 / (1.0 + (roll_up / (roll_down + 1e-9))))
            
        return df, info
    except: return pd.DataFrame(), {}

@st.cache_data(ttl=900, show_spinner=False)
def fetch_intel():
    intel = {"finance": [], "world": [], "iran": []}
    translator = GoogleTranslator(source='auto', target='zh-CN')
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get("https://www.cnbc.com/world-markets/", headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        for l in soup.select(".Card-title")[:5]:
            intel["finance"].append({"t": translator.translate(l.get_text(strip=True)), "l": "https://www.cnbc.com"+l.get('href') if not l.get('href').startswith("http") else l.get('href')})
    except: pass
    sources = ["http://feeds.bbci.co.uk/news/world/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml"]
    iran_kws = ["iran", "middle east", "israel", "hezbollah", "gaza", "伊朗", "中东", "以色列"]
    seen = set()
    for url in sources:
        try:
            r = requests.get(url, headers=headers, timeout=6)
            soup = BeautifulSoup(r.text, 'xml')
            for item in soup.find_all('item')[:6]:
                raw_t = item.title.text.strip()
                if raw_t not in seen:
                    seen.add(raw_t)
                    zh_t = translator.translate(raw_t)
                    link = item.link.text.strip()
                    if any(k in raw_t.lower() or k in zh_t for k in iran_kws):
                        intel["iran"].append({"t": zh_t, "l": link})
                    else:
                        intel["world"].append({"t": zh_t, "l": link})
        except: continue
    return intel

# --- 4. 侧边栏 ---
if 'my_stocks' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: st.session_state.my_stocks = json.load(f)
        except: st.session_state.my_stocks = ["GC=F", "160416", "000001"]
    else: st.session_state.my_stocks = ["GC=F", "160416", "000001"]

with st.sidebar:
    st.header("🛠️ 战略指挥部")
    st.write(f"🏠 {get_weather('Chengdu', '成都')} | 🏫 {get_weather('Mianyang', '绵阳')}")
    st.divider()
    new_in = st.text_input("➕ 接入新目标:").strip().upper()
    if st.button("确定接入", use_container_width=True):
        if new_in and new_in not in st.session_state.my_stocks:
            st.session_state.my_stocks.append(new_in)
            with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
            st.rerun()
    st.divider()
    if st.button("🔥 重置/清空所有", use_container_width=True, type="primary"):
        st.session_state.my_stocks = ["GC=F", "160416"]
        with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
        st.rerun()
    st.caption("v12.2_Pro 全周期拖拽版")

# --- 5. 主界面行情栏 ---
st.title("🛰️ 全球局势 & 金融命脉战略终端")

data_dict = {}
if st.session_state.my_stocks:
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(get_stock_data, st.session_state.my_stocks))
    data_dict = dict(zip(st.session_state.my_stocks, results))

if st.session_state.my_stocks:
    cols = st.columns(len(st.session_state.my_stocks))
    for i, t in enumerate(st.session_state.my_stocks):
        with cols[i]:
            df_q, info_q = data_dict.get(t, (pd.DataFrame(), {}))
            if not df_q.empty and len(df_q) >= 2:
                cur, prev = df_q['Close'].iloc[-1], df_q['Close'].iloc[-2]
                chg = cur - prev
                color = "#ff4b4b" if chg >= 0 else "#00eb93"
                st.markdown(f'<div class="metric-card"><div style="font-size:0.8em;color:gray;">{t}</div>'
                            f'<div style="font-size:1.1em;font-weight:bold;">{cur:,.2f}</div>'
                            f'<div style="color:{color};font-size:0.8em;">{"↑" if chg>=0 else "↓"} {abs(chg):.2f}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="metric-card"><div style="font-size:0.8em;color:gray;">{t}</div>'
                            f'<div style="font-size:1.1em;font-weight:bold;">N/A</div>'
                            f'<div style="color:gray;font-size:0.8em;">数据链路故障</div></div>', unsafe_allow_html=True)
            
            if st.button("❌ 移除", key=f"del_{t}_{i}", use_container_width=True):
                st.session_state.my_stocks.remove(t)
                with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
                st.rerun()

# 聚焦研判
if st.session_state.my_stocks:
    target = st.selectbox("🎯 聚焦研判目标:", options=st.session_state.my_stocks, key="target_selector")
    df_h, info_h = data_dict.get(target, (pd.DataFrame(), {}))
    
    if not df_h.empty and len(df_h) >= 2:
        l, r = st.columns([1, 2.5])
        with l:
            rsi = df_h['RSI'].iloc[-1] if 'RSI' in df_h.columns else 50
            advice = "💎 建议吸筹" if rsi < 30 else "🚀 强势看涨" if df_h['Close'].iloc[-1] > df_h['MA5'].iloc[-1] else "🟡 震荡整固"
            st.write(f"### {info_h.get('shortName', target)}")
            st.markdown(f'<div class="rec-hold">{advice}</div>', unsafe_allow_html=True)
            st.write(f"**RSI:** `{rsi:.2f}` | **现价:** `{df_h['Close'].iloc[-1]:,.2f}`")
            
            clean_target = target.upper().replace('.SS', '').replace('.SZ', '')
            if clean_target.isdigit() and len(clean_target) == 6:
                st.divider()
                st.write("🗣️ **东方财富股吧·前沿热议**")
                guba_posts = get_guba_posts(clean_target)
                if guba_posts:
                    for p in guba_posts:
                        st.markdown(f'<div class="guba-post">💬 <a href="{p["l"]}" target="_blank">{p["t"]}</a></div>', unsafe_allow_html=True)
                else:
                    st.caption("暂无最新讨论")

        with r:
            t_k, t_5d, t_intra = st.tabs(["📉 核心K线分析", "📈 五日图", "⏱️ 今日分时"])
            with t_k:
                # 🟢 [核心注入 1]: 全周期时间切片器 (包含日/周/月/建仓以来)
                k_type = st.radio("时间跨度:", ["日K(1个月)", "日K(1年)", "周K(1年)", "月K(3年)", "最大周K(建仓以来)"], index=0, horizontal=True, label_visibility="collapsed")
                
                # Pandas 数据重采样逻辑 (完全不影响原抓取代码，只是对画图数据进行切片合并)
                if "日K" in k_type:
                    df_plot = df_h.tail(22) if "1个月" in k_type else df_h.tail(250)
                else:
                    rule = 'W-FRI' if '周K' in k_type else 'ME'  # 重采样：周K按周五，月K按月末
                    df_res = df_h.resample(rule).agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
                    if 'MA5' in df_h.columns:
                        df_res['MA5'] = df_res['Close'].rolling(5).mean()
                        df_res['MA20'] = df_res['Close'].rolling(20).mean()
                    
                    if "1年" in k_type:
                        df_plot = df_res.tail(52)
                    elif "3年" in k_type:
                        df_plot = df_res.tail(36)
                    else:
                        df_plot = df_res

                fig = go.Figure(data=[go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], 
                    increasing_line_color='#ff4b4b', decreasing_line_color='#00eb93', name="K线")])
                
                if 'MA5' in df_plot.columns and 'MA20' in df_plot.columns:
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA5'], name="MA5", line=dict(color='#4a90e2', width=1.2)))
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], name="MA20", line=dict(color='#ffa500', width=1.2)))
                
                # 🟢 [核心注入 2]: 强制开启 dragmode='pan'，默认操作变为“平移拖拽”而不是框选放大
                if not df_plot.empty:
                    ymin, ymax = df_plot['Low'].min(), df_plot['High'].max()
                    pad = (ymax - ymin) * 0.05 if ymax != ymin else 0.1
                    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350, template="plotly_dark", xaxis_rangeslider_visible=False, yaxis=dict(range=[ymin - pad, ymax + pad]), dragmode='pan')
                else:
                    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350, template="plotly_dark", xaxis_rangeslider_visible=False, dragmode='pan')
                    
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
            
            with t_5d:
                df_5d = get_5d_data(target)
                if not df_5d.empty:
                    fig_5d = go.Figure(go.Scatter(x=df_5d['Time'], y=df_5d['Price'], mode='lines', line=dict(color='#4a90e2', width=2)))
                    ymin, ymax = df_5d['Price'].min(), df_5d['Price'].max()
                    pad = (ymax - ymin) * 0.05 if ymax != ymin else 0.1
                    fig_5d.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350, template="plotly_dark", yaxis=dict(range=[ymin - pad, ymax + pad]), dragmode='pan')
                    st.plotly_chart(fig_5d, use_container_width=True, config={'scrollZoom': True})
                else:
                    st.info("当前暂无五日图信号")

            with t_intra:
                df_intra = get_intraday_data(target)
                if not df_intra.empty:
                    fig_intra = go.Figure(go.Scatter(x=df_intra['Time'], y=df_intra['Price'], mode='lines', line=dict(color='#00eb93', width=2)))
                    ymin, ymax = df_intra['Price'].min(), df_intra['Price'].max()
                    pad = (ymax - ymin) * 0.05 if ymax != ymin else 0.1
                    fig_intra.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350, template="plotly_dark", yaxis=dict(range=[ymin - pad, ymax + pad]), dragmode='pan')
                    st.plotly_chart(fig_intra, use_container_width=True, config={'scrollZoom': True})
                else:
                    st.info("当前时间段暂无分时信号")

# 三大情报战区 UI 恢复
st.divider()
st.subheader("📡 综合情报汇总")
t1, t2, t3 = st.tabs(["📊 金融命脉", "🌐 全球热点", "🇮🇷 中东战区"])

intel = fetch_intel()

def render_news(items, cls_name, tag):
    if not items: st.write("🛰️ 暂无最新信号")
    for it in items:
        with st.expander(f"📌 {it['t'][:50]}..."):
            st.markdown(f'<span class="news-tag {cls_name}">{tag}</span> <b>{it["t"]}</b>', unsafe_allow_html=True)
            st.link_button("原文报道", it['l'])

with t1: render_news(intel["finance"], "tag-finance", "FINANCE")
with t2: render_news(intel["world"], "tag-world", "GLOBAL")
with t3: render_news(intel["iran"], "tag-iran", "MIDDLE-EAST")
