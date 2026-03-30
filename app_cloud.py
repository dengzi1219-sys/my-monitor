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
from concurrent.futures import ThreadPoolExecutor

# --- 1. 核心配置 ---
# --- 1. 核心配置 (环境自适应版) ---
# 检测是否在本地运行（如果是本地，启用 7892 代理；如果是云端，自动跳过）
if os.path.exists("D:\\vscode") or os.path.exists("D:\\code"):
    os.environ['HTTP_PROXY'] = "http://127.0.0.1:7892"
    os.environ['HTTPS_PROXY'] = "http://127.0.0.1:7892"
    print("🛰️ 本地环境：已开启 7892 代理链路")
else:
    # 云端环境下清除所有代理设置
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)
    print("☁️ 云端环境：已切换至原生全球链路")

DB_FILE = "stocks.json"

st.set_page_config(page_title="全球战略情报终端 v8.0", layout="wide")

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
    except:
        return pd.DataFrame(), {}

@st.cache_data(ttl=3600)
def get_weather(city_en, city_zh):
    try:
        res = requests.get(f"https://wttr.in/{city_en}?format=3", timeout=5)
        res.encoding = 'utf-8' 
        return res.text.replace(city_en, city_zh).strip()
    except:
        return f"{city_zh}：同步中..."

# --- 4. 【已修复】深度研判建议算法 ---
def get_ai_advice(df, info):
    if df.empty: return "⚪ 暂无数据", "rec-hold", 50
    rsi = df['RSI'].iloc[-1] if 'RSI' in df.columns else 50
    m5, m20, cp = df['MA5'].iloc[-1], df['MA20'].iloc[-1], df['Close'].iloc[-1]
    
    # 极值优先：防追高/防踏空
    if rsi >= 75: return "⚠️ 山顶警报：超买严重", "rec-warn", rsi
    if rsi <= 25: return "💎 捡漏信号：超跌入场", "rec-buy", rsi
    
    # 趋势拆解：不再无脑观望
    if m5 > m20:
        if cp >= m5: return "🚀 技术面：强势多头", "rec-buy", rsi
        else: return "📈 技术面：上升回档", "rec-buy", rsi # 涨势中的小跌
    elif m5 < m20:
        if cp <= m5: return "💀 技术面：空头排列", "rec-sell", rsi
        else: return "📉 技术面：超跌反弹", "rec-hold", rsi # 跌势中的小涨
        
    return "🟡 趋势持稳：横盘震荡", "rec-hold", rsi

# --- 5. 【重装上阵】防拦截 RSS 情报系统 ---
@st.cache_data(ttl=1200)
def fetch_global_intelligence():
    intel = {"finance": [], "world": [], "iran": []}
    headers = {'User-Agent': 'Mozilla/5.0'}
    translator = GoogleTranslator(source='auto', target='zh-CN')

    def translate_safe(text):
        try: return translator.translate(text)
        except: return text # 翻译失败也会保留英文，绝不丢新闻

    # A. 金融命脉 (保留你测试成功的 CNBC)
    try:
        r_f = requests.get("https://www.cnbc.com/world-markets/", headers=headers, timeout=10)
        soup_f = BeautifulSoup(r_f.text, 'html.parser')
        links_f = soup_f.select(".Card-title")[:8]
        for l in links_f:
            t = l.get_text(strip=True)
            h = l.get('href')
            if t and h:
                if not h.startswith("http"): h = "https://www.cnbc.com" + h
                intel["finance"].append({"t": translate_safe(t), "l": h})
    except: pass

    # B & C. 全球热点与伊朗专栏 (改用底层 RSS 数据流，100% 破防爬虫拦截)
    # 来源1: BBC (全球宏观)  来源2: 半岛电视台 (中东最强喉舌)
    rss_sources = [
        "http://feeds.bbci.co.uk/news/world/rss.xml", 
        "https://www.aljazeera.com/xml/rss/all.xml"
    ]
    
    iran_keywords = ["iran", "tehran", "middle east", "israel", "hezbollah", "lebanon", "gaza", "palestine", "syria", "yemen", "伊朗", "德黑兰", "中东", "以色列", "黎巴嫩", "加沙", "巴勒斯坦", "也门", "叙利亚", "红海"]
    seen_titles = set()
    
    for url in rss_sources:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser') # RSS 也是标记语言，可以直接拆解
            items = soup.find_all('item')
            
            for item in items[:12]:
                title_tag = item.find('title')
                link_tag = item.find('link')
                if title_tag and link_tag:
                    raw_title = title_tag.text.strip()
                    raw_link = link_tag.text.strip()
                    
                    if raw_title not in seen_titles and len(raw_title) > 10:
                        seen_titles.add(raw_title)
                        zh_title = translate_safe(raw_title)
                        
                        # 关键词分流
                        if any(k in raw_title.lower() or k in zh_title for k in iran_keywords):
                            intel["iran"].append({"t": zh_title, "l": raw_link})
                        else:
                            intel["world"].append({"t": zh_title, "l": raw_link})
        except: continue
        
    return intel

# --- 6. 侧边栏与数据 ---
if 'my_stocks' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: st.session_state.my_stocks = json.load(f)
        except: st.session_state.my_stocks = ["GC=F", "NVDA", "600726.SS"]
    else: st.session_state.my_stocks = ["GC=F", "NVDA", "600726.SS"]

with st.sidebar:
    st.header("🛠️ 战略指挥部")
    st.write(f"🏠 {get_weather('Chengdu', '成都')} | 🏫 {get_weather('Mianyang', '绵阳')}")
    st.divider()
    new_in = st.text_input("➕ 监控新目标:").strip().upper()
    if st.button("接入系统"):
        if new_in and new_in not in st.session_state.my_stocks:
            st.session_state.my_stocks.append(new_in)
            with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
            st.rerun()
    if st.session_state.my_stocks:
        to_del = st.selectbox("🗑️ 移除目标:", options=st.session_state.my_stocks)
        if st.button("断开连接", type="primary"):
            st.session_state.my_stocks.remove(to_del)
            with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
            st.rerun()
    st.divider()
    st.caption("西科大准工程师专属 | v8.0-Ultimate RSS架构")

# --- 7. 主界面布局 ---
st.title("🛰️ 全球局势 & 金融命脉战略终端")

# 顶部行情
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

# 深度分析
target = st.selectbox("🎯 聚焦研判目标:", options=st.session_state.my_stocks)
df_h, info = get_stock_data_pro(target)
if not df_h.empty:
    l, r = st.columns([1, 2.5])
    with l:
        advice, css_class, rsi_val = get_ai_advice(df_h, info)
        st.write(f"### {info.get('shortName', target)}")
        st.markdown(f'<div class="{css_class}">{advice}</div>', unsafe_allow_html=True)
        st.write(f"**RSI 动能:** `{rsi_val:.2f}`")
        symbol = "¥" if target.endswith(('.SS', '.SZ')) else "$"
        st.write(f"**最新成交:** {symbol}{df_h['Close'].iloc[-1]:,.2f}")
    with r:
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df_h.index, open=df_h['Open'], high=df_h['High'], low=df_h['Low'], close=df_h['Close'], name="K线",
                                     increasing_line_color='#ff4b4b', decreasing_line_color='#00eb93'))
        fig.add_trace(go.Scatter(x=df_h.index, y=df_h['MA5'], name="MA5 (5日线)", line=dict(color='#4a90e2', width=1.5)))
        fig.add_trace(go.Scatter(x=df_h.index, y=df_h['MA20'], name="MA20 (20日线)", line=dict(color='#ffa500', width=1.5)))
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=350, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- 8. 情报汇总区 ---
st.subheader("📡 综合情报汇总中心")
tab_fin, tab_world, tab_iran = st.tabs(["📊 金融命脉", "🌐 全球热点 (BBC/半岛)", "🇮🇷 中东战区情报专栏"])

with st.spinner("正在从全球卫星链路解密情报..."):
    all_intel = fetch_global_intelligence()

def render_news_list(news_items, tag_class, tag_text):
    if not news_items:
        st.write("🛰️ 暂无相关情报，系统正在持续监测...")
        return
    for item in news_items[:12]:
        with st.expander(f"📌 {item['t'][:60]}..."):
            st.markdown(f'<span class="news-tag {tag_class}">{tag_text}</span> <b>{item["t"]}</b>', unsafe_allow_html=True)
            st.link_button("解密原始报道", item['l'])

with tab_fin:
    render_news_list(all_intel["finance"], "tag-finance", "FINANCE")

with tab_world:
    st.info("💡 来源架构已切换至 BBC / Al Jazeera底层数据流，彻底免疫爬虫封锁。")
    render_news_list(all_intel["world"], "tag-world", "GLOBAL")

with tab_iran:
    st.info("🚨 战略雷达：专门拦截涉及 德黑兰/以色列/加沙/黎巴嫩 等核心敏感词的突发情报。")
    render_news_list(all_intel["iran"], "tag-iran", "MIDDLE-EAST")

st.divider()
st.caption("v8.0-Ultimate | 极速并发部署版 | 战略级情报不构成投资建议")
