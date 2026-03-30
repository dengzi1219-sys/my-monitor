import os
import json

# ==========================================
# 🛰️ 环境切换开关（本地测试必改！）
# ==========================================
# 🛑 在【成都/绵阳宿舍】测试时，请删掉下面两行开头的 # 号
# 🚀 上传到【GitHub 云端】前，请务必在下面两行开头加上 # 号
#os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7892'
#os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7892'

# --- 以下是主程序，请勿随意改动顺序 ---
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor

# 1. 基础配置
DB_FILE = "stocks.json"
st.set_page_config(page_title="全球情报终端 v7.1-Cloud", layout="wide")

# 2. 视觉样式 (CSS)
st.markdown("""
    <style>
    .metric-card {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
    }
    .status-up { color: #ff3333; font-weight: bold; }
    .status-down { color: #00ff88; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 3. 核心工具函数
@st.cache_data(ttl=600)
def get_stock_data_pro(ticker):
    try:
        t_obj = yf.Ticker(ticker)
        df = t_obj.history(period="3mo")
        if not df.empty:
            df['MA5'] = df['Close'].rolling(window=5).mean()
        return df, t_obj.info
    except:
        return pd.DataFrame(), {}

@st.cache_data(ttl=3600)
def get_weather(city_en, city_zh):
    try:
        res = requests.get(f"https://wttr.in/{city_en}?format=3", timeout=10)
        res.encoding = 'utf-8' 
        return res.text.replace(city_en, city_zh).strip()
    except:
        return f"{city_zh}：同步中..."

# 4. 数据初始化
if 'my_stocks' not in st.session_state:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: 
                st.session_state.my_stocks = json.load(f)
        except: 
            st.session_state.my_stocks = ["GC=F", "NVDA", "600519.SS"]
    else:
        st.session_state.my_stocks = ["GC=F", "NVDA", "600519.SS"]

# 5. 侧边栏控制
with st.sidebar:
    st.header("🛰️ 终端控制中心")
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_cd = executor.submit(get_weather, 'Chengdu', '成都')
        f_my = executor.submit(get_weather, 'Mianyang', '绵阳')
        st.write(f"🏠 {f_cd.result()}")
        st.write(f"🏫 {f_my.result()}")
    
    st.divider()
    st.subheader("📦 资产库管理")
    new_in = st.text_input("➕ 添加代码:").strip().upper()
    if st.button("同步项目", use_container_width=True):
        if new_in:
            if new_in.isdigit():
                new_in = f"{new_in}.SS" if new_in.startswith(('60', '68')) else f"{new_in}.SZ"
            if new_in not in st.session_state.my_stocks:
                st.session_state.my_stocks.append(new_in)
                with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
                st.rerun()

    if st.session_state.my_stocks:
        to_del = st.selectbox("🗑️ 移除代码:", options=st.session_state.my_stocks)
        if st.button("🔥 确认删除", use_container_width=True, type="primary"):
            st.session_state.my_stocks.remove(to_del)
            with open(DB_FILE, 'w') as f: json.dump(st.session_state.my_stocks, f)
            st.rerun()
    
    st.divider()
    st.subheader("🎓 校园情报")
    st.markdown(f'📍 <b>西南科技大学</b><br>🧬 生物工程专业<br>🎮 键盘锁 (1999) 守护中', unsafe_allow_html=True)

# 6. 主界面
st.title("🛰️ 全球局势 & 校园生活复合终端 7.1-Cloud")

if st.session_state.my_stocks:
    stock_cols = st.columns(len(st.session_state.my_stocks))
    with ThreadPoolExecutor(max_workers=len(st.session_state.my_stocks)) as executor:
        list(executor.map(get_stock_data_pro, st.session_state.my_stocks))
        
    for idx, ticker in enumerate(st.session_state.my_stocks):
        with stock_cols[idx]:
            df_q, _ = get_stock_data_pro(ticker)
            if not df_q.empty:
                price = df_q['Close'].iloc[-1]
                change = price - df_q['Close'].iloc[-2]
                st.markdown(f"""<div class="metric-card"><div style="color:gray;font-size:0.8em;">{ticker}</div>
                <div style="font-size:1.1em;font-weight:bold;">${price:,.2f}</div>
                <div style="color:{'#00ff88' if change < 0 else '#ff3333'};font-size:0.8em;">
                {'↓' if change < 0 else '↑'} {abs(change):.2f}</div></div>""", unsafe_allow_html=True)

st.divider()

# 7. 详情区
@st.fragment
def render_market_view():
    st.subheader("📊 深度研判")
    target = st.selectbox("分析目标:", options=st.session_state.my_stocks)
    df_h, t_i = get_stock_data_pro(target)
    if not df_h.empty:
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df_h.index, open=df_h['Open'], high=df_h['High'], low=df_h['Low'], close=df_h['Close'], 
                                     increasing_line_color='#ff3333', decreasing_line_color='#00ff88'))
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False,
                          template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

render_market_view()

# 8. 情报区
@st.cache_data(ttl=900)
def get_news_with_links():
    results = []
    try:
        # AP News 这种网站通常需要代理才能从国内访问
        res = requests.get("https://apnews.com/hub/world-news", timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        headlines = soup.find_all(['h3', 'h2'])[:6]
        
        def process_news(h):
            text = h.get_text(strip=True)
            link = h.find('a')
            if link and len(text) > 25:
                href = link['href']
                if not href.startswith("http"): href = "https://apnews.com" + href
                try:
                    zh = GoogleTranslator(source='auto', target='zh-CN').translate(text)
                    return {"t": zh, "l": href}
                except: pass
            return None

        with ThreadPoolExecutor(max_workers=6) as executor:
            res_list = list(executor.map(process_news, headlines))
            results = [r for r in res_list if r]
    except: pass
    return results

st.subheader("🌐 全球局势实时情报")
news_feed = get_news_with_links()
for item in news_feed:
    st.info(f"🔹 {item['t']}")
    st.markdown(f"[🔗 查看深度报道原文]({item['l']})")

st.divider()
st.caption("v7.1-Cloud | 极速并发部署版 | 西科大实验室运行中")