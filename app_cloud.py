import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from bs4 import BeautifulSoup
import os
import json
from deep_translator import GoogleTranslator

# --- 1. 核心配置 (环境自适应版) ---
if os.path.exists("D:\\vscode") or os.path.exists("D:\\code") or os.path.exists("D:\\cloud"):
    os.environ['HTTP_PROXY'] = "http://127.0.0.1:7892"
    os.environ['HTTPS_PROXY'] = "http://127.0.0.1:7892"
else:
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)

DB_FILE = "stocks.json"
st.set_page_config(page_title="全球战略情报终端 v8.2", layout="wide")

# --- 2. 视觉样式 (CSS) ---
st.markdown("""
    <style>
    .metric-card { border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 12px; margin-bottom: 10px; }
    .rec-buy { color: #ff4b4b; font-weight: bold; background: rgba(255, 75, 75, 0.1); padding: 5px 10px; border-radius: 4px; border: 1px solid #ff4b4b; }
    .rec-sell { color: #00eb93; font-weight: bold; background: rgba(0, 235, 147, 0.1); padding: 5px 10px; border-radius: 4px; border: 1px solid #00eb93; }
    .rec-hold { color: #ffa500; font-weight: bold; background: rgba(255, 165, 0, 0.1); padding: 5px 10px; border-radius: 4px; border: 1px solid #ffa500; }
    .rec-warn { color: #ffffff; font-weight: bold; background: #8b0000; padding: 5px 10px; border-radius: 4px; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.5; } }
    .news-tag { font-size: 0.7em; padding: 2px 6px; border-radius: 10px; margin-right: 5px; color: white; }
    .tag-finance { background-color: #4a90e2; }
    .tag-world { background-color: #e2a14a; }
    .tag-iran { background-color: #d0021b; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心工具函数 ---
@st.cache_data(ttl=3600)
def get_weather(city_en, city_zh):
    try:
        res = requests.get(f"https://wttr.in/{city_en}?format=3", timeout=3)
        res.encoding = 'utf-8' 
        return res.text.replace(city_en, city_zh).strip()
    except: return f"{city_zh}：天气同步失败"

@st.cache_data(ttl=300)
def get_stock_data_pro(ticker):
    try:
        t_obj = yf.Ticker(ticker)
        df = t_obj.history(period="6mo")
        if not df.empty and len(df) > 20:
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        return df, t_obj.info
    except: return pd.DataFrame(), {}

def get_ai_advice(df, info):
    if df.empty: return "⚪ 暂无数据", "rec-hold", 50
    rsi = df['RSI'].iloc[-1] if 'RSI' in df.columns else 50
    m5, m20, cp = df['MA5'].iloc[-1], df['MA20'].iloc[-1], df['Close'].iloc[-1]
    if rsi >= 75: return "⚠️ 山顶警报：超买严重", "rec-warn", rsi
    if rsi <= 25: return "💎 捡漏信号：超跌入场", "rec-buy", rsi
    if m5 > m20:
        if cp >= m5: return "🚀 技术面：强势多头", "rec-buy", rsi
        else: return "📈 技术面：上升回档", "rec-buy", rsi
    elif m5 < m20:
        if cp <= m5: return "💀 技术面：空头排列", "rec-sell", rsi
        else: return "📉 技术面：超跌反弹", "rec-hold", rsi
    return "🟡 趋势持稳：横盘震荡", "rec-hold", rsi

@st.cache_data(ttl=1200)
def fetch_global_intelligence():
    intel = {"finance": [], "world": [], "iran": []}
    headers = {'User-Agent': 'Mozilla/5.0'}
    translator = GoogleTranslator(source='auto', target='zh-CN')
    def trans_safe(text):
        try: return translator.translate(text)
        except: return text
    # CNBC Finance
    try:
        r = requests.get("https://www.cnbc.com/world-markets/", headers=headers, timeout=4)
        soup = BeautifulSoup(r.text, 'html.parser')
        for l in soup.select(".Card-title")[:6]:
            intel["finance"].append({"t": trans_safe(l.get_text(strip=True)), "l": "https://www.cnbc.com"+l.get('href') if not l.get('href').startswith("http") else l.get('href')})
    except: pass
    # RSS Global & Iran
    rss = ["http://feeds.bbci.co.uk/news/world/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml"]
    iran_kws = ["iran", "tehran", "middle east", "israel", "hezbollah", "lebanon", "gaza", "伊朗", "德黑兰", "中东", "以色列"]
    seen = set()
    for url in rss:
        try:
            r = requests.get(url, headers=headers, timeout=4)
            soup = BeautifulSoup(r.text, 'xml')
            for item in soup.find_all('item')[:8]:
                raw_t = item.title.text.strip()
                if raw_t not in seen:
                    seen.add(raw_t)
                    zh_t = trans_safe(raw_t)
                    link = item.link.text.strip()
                    if any(k in raw_t.lower() or k in zh_t for k in iran_kws): intel["iran"].append({"t": zh_t, "l": link})
                    else: intel["world"].append({"t": zh_t, "l": link})
        except: continue
    return intel

# --- 4. 数据初始化 ---
if 'my_stocks' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: st.session_state.my_stocks = json.load(f)
        except: st.session_state.my_stocks = ["GC=F", "NVDA", "600726.SS"]
    else: st.session_state.my_stocks = ["GC=F", "NVDA", "600726.SS"]

# --- 5. 【加回侧边栏】 ---
with st.sidebar:
    st.header("🛠️ 战略指挥部")
    st.write(f"🏠 {get_weather('Chengdu', '成都')} | 🏫 {get_weather('Mianyang', '绵阳')}")
    st.divider()
    new_in = st.text_input("➕ 监控新目标 (如 NVDA):").strip().upper()
    if st.button("接入系统", use_container_width=True):
        if new_in and new_in not in st.session_state.my_stocks:
            st.session_state.my_stocks.append(new_in)
            with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
            st.rerun()
    if st.session_state.my_stocks:
        to_del = st.selectbox("🗑️ 移除目标:", options=st.session_state.my_stocks)
        if st.button("断开连接", use_container_width=True, type="primary"):
            st.session_state.my_stocks.remove(to_del)
            with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
            st.rerun()
    st.divider()
    st.caption("西科大准工程师专属 | v8.2-Final")

# --- 6. 主界面 ---
st.title("🛰️ 全球局势 & 金融命脉战略终端")

if st.session_state.my_stocks:
    cols = st.columns(len(st.session_state.my_stocks))
    for i, t in enumerate(st.session_state.my_stocks):
        df_q, _ = get_stock_data_pro(t)
        if not df_q.empty:
            cur, prev = df_q['Close'].iloc[-1], df_q['Close'].iloc[-2]
            chg = cur - prev
            with cols[i]:
                st.markdown(f'<div class="metric-card"><div style="font-size:0.8em;color:gray;">{t}</div>'
                            f'<div style="font-size:1.1em;font-weight:bold;">{cur:,.2f}</div>'
                            f'<div style="color:{"#ff4b4b" if chg>0 else "#00eb93"};font-size:0.8em;">'
                            f'{"↑" if chg>0 else "↓"} {abs(chg):.2f}</div></div>', unsafe_allow_html=True)

target = st.selectbox("🎯 聚焦研判目标:", options=st.session_state.my_stocks)
df_h, info = get_stock_data_pro(target)
if not df_h.empty:
    l, r = st.columns([1, 2.5])
    with l:
        advice, css, rsi = get_ai_advice(df_h, info)
        st.write(f"### {info.get('shortName', target)}")
        st.markdown(f'<div class="{css}">{advice}</div>', unsafe_allow_html=True)
        st.write(f"**RSI 动能:** `{rsi:.2f}`")
        st.write(f"**最新成交:** `{df_h['Close'].iloc[-1]:,.2f}`")
    with r:
        fig = go.Figure(data=[go.Candlestick(x=df_h.index, open=df_h['Open'], high=df_h['High'], low=df_h['Low'], close=df_h['Close'], name="K线")])
        fig.add_trace(go.Scatter(x=df_h.index, y=df_h['MA5'], name="MA5", line=dict(color='#4a90e2', width=1.5)))
        fig.add_trace(go.Scatter(x=df_h.index, y=df_h['MA20'], name="MA20", line=dict(color='#ffa500', width=1.5)))
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("📡 综合情报汇总中心")
tab_fin, tab_world, tab_iran = st.tabs(["📊 金融命脉", "🌐 全球热点", "🇮🇷 中东战区"])
intel = fetch_global_intelligence()

def render(items, cls, tag):
    if not items: st.write("🛰️ 正在监听信号..."); return
    for it in items[:10]:
        with st.expander(f"📌 {it['t'][:55]}..."):
            st.markdown(f'<span class="news-tag {cls}">{tag}</span> <b>{it["t"]}</b>', unsafe_allow_html=True)
            st.link_button("解密原始报道", it['l'])

with tab_fin: render(intel["finance"], "tag-finance", "FINANCE")
with tab_world: render(intel["world"], "tag-world", "GLOBAL")
with tab_iran: render(intel["iran"], "tag-iran", "MIDDLE-EAST")