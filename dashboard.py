import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import os
from datetime import datetime, timedelta
import numpy as np

# ==========================================
# 1. إعدادات الصفحة والتصميم
# ==========================================
st.set_page_config(
    page_title="منصة التداول الاحترافية",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. CSS مخصص للتصميم الاحترافي
# ==========================================
CUSTOM_CSS = """
<style>
/* الخلفية الرئيسية */
.stApp {
    background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
    color: #e0e0e0;
}

/* الشريط الجانبي */
.css-1d391kg {
    background: linear-gradient(180deg, #0f1429 0%, #1a1f3a 100%);
}

/* العناوين */
h1, h2, h3 {
    color: #ffffff;
    font-family: 'Segoe UI', Tahoma, sans-serif;
}

/* البطاقات */
.stMetric {
    background: linear-gradient(135deg, #1e2746 0%, #2a3560 100%);
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #3a4570;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}

/* الأزرار */
.stButton>button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: bold;
    transition: all 0.3s;
}

.stButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

/* الجداول */
.dataframe {
    background: #1e2746;
    color: #e0e0e0;
    border-radius: 10px;
    overflow: hidden;
}

/* شريط التمرير */
::-webkit-scrollbar {
    width: 10px;
}
::-webkit-scrollbar-track {
    background: #0a0e27;
}
::-webkit-scrollbar-thumb {
    background: #667eea;
    border-radius: 5px;
}

/* التحذيرات */
.stAlert {
    background: #1e2746;
    border-radius: 10px;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==========================================
# 3. إعدادات الأسواق
# ==========================================
MARKETS = {
    "🇺🇸 الأسواق الأمريكية": {
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY", "META", "GOOGL", "AMD", "NFLX"],
        "color": "#00d4ff",
        "icon": "🇸"
    },
    "🇸🇦 السوق السعودي": {
        "symbols": ["2222.SR", "1120.SR", "2010.SR", "1150.SR", "2280.SR", "1211.SR"],
        "color": "#00ff88",
        "icon": "🇸🇦"
    },
    "🇦🇪 السوق الإماراتي": {
        "symbols": ["ADCB.AD", "FAB.AD", "EMAAR.DU", "DIB.AD", "ALDAR.AD"],
        "color": "#ff6b6b",
        "icon": "🇦🇪"
    },
    "💰 العملات الرقمية": {
        "symbols": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD"],
        "color": "#ffd93d",
        "icon": "💰"
    },
    "💱 الفوركس": {
        "symbols": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X"],
        "color": "#c084fc",
        "icon": ""
    },
    "🥇 المعادن والمؤشرات": {
        "symbols": ["GC=F", "SI=F", "^GSPC", "^DJI", "^IXIC", "^VIX"],
        "color": "#fb923c",
        "icon": "🥇"
    }
}

# ==========================================
# 4. دوال مساعدة
# ==========================================
@st.cache_data(ttl=300)
def fetch_stock_data(symbol, period="3mo"):
    """جلب بيانات السهم"""
    try:
        df = yf.Ticker(symbol).history(period=period)
        if df.empty:
            return None
        return df
    except:
        return None

def calculate_indicators(df):
    """حساب المؤشرات الفنية"""
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['BB_Upper'] = df['Close'].rolling(20).mean() + 2 * df['Close'].rolling(20).std()
    df['BB_Lower'] = df['Close'].rolling(20).mean() - 2 * df['Close'].rolling(20).std()
    return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_signal(price, rsi, support, resistance):
    """تحديد الإشارة"""
    if price <= support * 1.02 and rsi < 35:
        return "شراء قوي 🟢", "#00ff88"
    elif price >= resistance * 0.98 and rsi > 65:
        return "بيع قوي 🔴", "#ff4757"
    elif rsi < 40:
        return "شراء ", "#ffd93d"
    elif rsi > 60:
        return "بيع 🟠", "#fb923c"
    return "مراقبة ⚪", "#a0a0a0"

# ==========================================
# 5. الشريط الجانبي
# ==========================================
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px;">
        <h2 style="color: #667eea; margin: 0;"> منصة التداول</h2>
        <p style="color: #a0a0a0; font-size: 12px;">Professional Trading Platform</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # حالة البوت
    st.markdown("###  حالة النظام")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("البوت", "نشط ✅")
    with col2:
        st.metric("Alpaca", "متصل 🔗")
    
    st.markdown("---")
    
    # التنقل بين الأقسام
    st.markdown("### 🧭 التنقل")
    page = st.radio(
        "اختر القسم:",
        [
            " لوحة التحكم",
            "🇺 الأسواق الأمريكية",
            "🇸 السوق السعودي",
            "🇦 السوق الإماراتي",
            "💰 العملات الرقمية",
            "💱 الفوركس",
            "🥇 المعادن والمؤشرات",
            "🧠 تحليل LSTM",
            "⚙️ الإعدادات"
        ],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # معلومات سريعة
    st.markdown("###  معلومات السوق")
    now = datetime.now()
    st.info(f"**التاريخ:** {now.strftime('%Y-%m-%d')}")
    st.info(f"**الوقت:** {now.strftime('%H:%M:%S')}")

# ==========================================
# 6. الصفحات
# ==========================================

# === صفحة لوحة التحكم ===
if page == "📊 لوحة التحكم":
    st.markdown("""
    <h1 style="text-align: center; color: #667eea; font-size: 48px;">
        📊 لوحة التحكم الرئيسية
    </h1>
    <p style="text-align: center; color: #a0a0a0;">
        نظرة شاملة على جميع الأسواق
    </p>
    """, unsafe_allow_html=True)
    
    # بطاقات KPI
    st.markdown("### 📈 المؤشرات الرئيسية")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.metric("الأسهم المراقبة", "38", "")
    with kpi2:
        st.metric("الإشارات النشطة", "5", "🔔")
    with kpi3:
        st.metric("الصفقات اليوم", "3", "💼")
    with kpi4:
        st.metric("الربح/الخسارة", "+$125.50", "+2.5%")
    
    st.markdown("---")
    
    # عرض الأسواق
    st.markdown("###  نظرة عامة على الأسواق")
    
    for market_name, market_data in MARKETS.items():
        with st.expander(f"{market_name} - {len(market_data['symbols'])} أصل", expanded=False):
            cols = st.columns(3)
            for i, symbol in enumerate(market_data['symbols'][:6]):
                with cols[i % 3]:
                    df = fetch_stock_data(symbol, "1mo")
                    if df is not None and len(df) > 0:
                        current_price = df['Close'].iloc[-1]
                        prev_price = df['Close'].iloc[-2] if len(df) > 1 else current_price
                        change = ((current_price - prev_price) / prev_price) * 100
                        
                        color = "#00ff88" if change >= 0 else "#ff4757"
                        arrow = "📈" if change >= 0 else "📉"
                        
                        st.markdown(f"""
                        <div style="background: #1e2746; padding: 15px; border-radius: 10px; border-left: 4px solid {color};">
                            <h4 style="margin: 0; color: white;">{symbol}</h4>
                            <p style="margin: 5px 0; font-size: 24px; color: {color}; font-weight: bold;">
                                ${current_price:.2f} {arrow}
                            </p>
                            <p style="margin: 0; color: {color}; font-size: 14px;">
                                {change:+.2f}%
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

# === صفحات الأسواق ===
elif page in ["🇺 الأسواق الأمريكية", "🇸🇦 السوق السعودي", "🇦🇪 السوق الإماراتي", 
              "💰 العملات الرقمية", "💱 الفوركس", "🥇 المعادن والمؤشرات"]:
    
    market_data = MARKETS[page]
    
    st.markdown(f"""
    <h1 style="color: {market_data['color']};">
        {market_data['icon']} {page}
    </h1>
    <p style="color: #a0a0a0;">
        تحليل شامل لـ {len(market_data['symbols'])} أصل
    </p>
    """, unsafe_allow_html=True)
    
    # اختيار السهم
    selected_symbol = st.selectbox(
        "اختر السهم للتحليل:",
        market_data['symbols'],
        key=f"select_{page}"
    )
    
    if selected_symbol:
        df = fetch_stock_data(selected_symbol, "6mo")
        
        if df is not None:
            df = calculate_indicators(df)
            
            # معلومات السهم
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
            
            high_52w = df['High'].max()
            low_52w = df['Low'].min()
            avg_volume = df['Volume'].mean()
            
            # KPIs
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("السعر الحالي", f"${current_price:.2f}", f"{change_pct:+.2f}%")
            with col2:
                st.metric("أعلى 52 أسبوع", f"${high_52w:.2f}")
            with col3:
                st.metric("أدنى 52 أسبوع", f"${low_52w:.2f}")
            with col4:
                st.metric("متوسط الحجم", f"{avg_volume:,.0f}")
            with col5:
                rsi_current = df['RSI'].iloc[-1]
                st.metric("RSI", f"{rsi_current:.1f}")
            
            st.markdown("---")
            
            # الرسم البياني الرئيسي
            st.markdown("### 📈 الرسم البياني التفاعلي")
            
            fig = make_subplots(
                rows=2
