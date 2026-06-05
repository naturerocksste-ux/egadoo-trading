import streamlit as st
from streamlit_autorefresh import st_autorefresh
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
import warnings
import requests
import json
import os
from PIL import Image
from io import BytesIO
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb

warnings.filterwarnings("ignore")

# ==========================================
# 1. إعدادات الصفحة والمظهر
# ==========================================
st.set_page_config(page_title="منصة التداول الشاملة Ultimate", layout="wide", page_icon="🚀")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');
    * { font-family: 'Tajawal', sans-serif; }
    .main-header { font-size: 2.5rem; font-weight: 800; text-align: center; margin-bottom: 20px; color: #1E88E5; }
    .company-info { background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%); padding: 20px; border-radius: 15px; color: white; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    .live-indicator { display: inline-block; width: 12px; height: 12px; background-color: #00E676; border-radius: 50%; animation: pulse 1.5s infinite; margin-right: 10px; box-shadow: 0 0 10px #00E676; }
    @keyframes pulse { 0% {box-shadow: 0 0 0 0 rgba(0, 230, 118, 0.7);} 70% {box-shadow: 0 0 0 10px rgba(0, 230, 118, 0);} 100% {box-shadow: 0 0 0 0 rgba(0, 230, 118, 0);} }
    .signal-box { padding: 15px; border-radius: 10px; font-weight: bold; font-size: 1.1rem; margin: 10px 0; box-shadow: 0 4px 10px rgba(0,0,0,0.1); color: white; }
    .buy-signal { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .sell-signal { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); }
    .hold-signal { background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%); }
    .warning-box { padding: 15px; border-radius: 10px; font-weight: bold; margin: 10px 0; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }
    .success-box { padding: 15px; border-radius: 10px; font-weight: bold; margin: 10px 0; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }
    .stop-loss-box { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%); padding: 20px; border-radius: 15px; color: white; box-shadow: 0 5px 15px rgba(0,0,0,0.2); margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

st_autorefresh(interval=15000, limit=None, key="live_refresh")

# ==========================================
# 2. إدارة الملفات والجلسة
# ==========================================
PORTFOLIO_FILE = "portfolio.json"
RISK_CONFIG_FILE = "risk_config.json"

def load_json(file, default):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_json(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

if 'portfolio' not in st.session_state: st.session_state.portfolio = load_json(PORTFOLIO_FILE, {"trades": [], "balance": 10000, "daily_loss": 0, "last_reset_date": datetime.date.today().strftime('%Y-%m-%d')})
if 'risk_config' not in st.session_state: st.session_state.risk_config = load_json(RISK_CONFIG_FILE, {"daily_loss_limit": 2.0, "max_consecutive_losses": 3, "min_volume_ratio": 1.0})
if 'company_info_cache' not in st.session_state: st.session_state.company_info_cache = {}

today = datetime.date.today().strftime('%Y-%m-%d')
if st.session_state.portfolio.get('last_reset_date') != today:
    st.session_state.portfolio['daily_loss'] = 0
    st.session_state.portfolio['last_reset_date'] = today
    save_json(PORTFOLIO_FILE, st.session_state.portfolio)

GLOBAL_MARKETS = {
    "[US] السوق الأمريكي": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY"],
    "[SA] السوق السعودي": ["2222.SR", "1120.SR", "2010.SR", "1150.SR", "2280.SR"],
    "[AE] السوق الإماراتي": ["ADCB.AD", "FAB.AD", "EMAAR.DU", "DIB.AD", "ALDAR.AD"],
    "[Crypto] العملات الرقمية": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "[Global] المعادن والمؤشرات": ["GC=F", "SI=F", "^GSPC", "^DJI", "^IXIC"],
    "[Forex] الفوركس": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"]
}

if 'current_market' not in st.session_state:
    st.session_state.current_market = "[US] السوق الأمريكي"
    st.session_state.watchlist = GLOBAL_MARKETS[st.session_state.current_market].copy()
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = st.session_state.watchlist[0]

# ==========================================
# 3. الدوال المساعدة
# ==========================================
def get_company_info(ticker):
    try:
        if ticker in st.session_state.company_info_cache: return st.session_state.company_info_cache[ticker]
        stock = yf.Ticker(ticker)
        info = stock.info
        company_name = info.get('longName', info.get('shortName', ticker))
        sector = info.get('sector', 'غير محدد')
        industry = info.get('industry', 'غير محدد')
        logo_url = None
        try:
            clean_ticker = ticker.replace('.SR','').replace('.CA','').replace('.AD','').replace('.DU','').replace('-USD','').replace('=X','').lower()
            logo_url = f"https://logo.clearbit.com/{clean_ticker}.com"
        except: pass
        company_data = {'name': company_name, 'sector': sector, 'industry': industry, 'logo_url': logo_url}
        st.session_state.company_info_cache[ticker] = company_data
        return company_data
    except: return {'name': ticker, 'sector': 'غير محدد', 'industry': 'غير محدد', 'logo_url': None}

def analyze_sentiment(news_list):
    if not news_list: return 50, "محايد"
    pos_words = ['up', 'rise', 'gain', 'growth', 'profit', 'beat', 'strong', 'bullish', 'rally', 'surge', 'record', 'high', 'increase', 'positive', 'success', 'upgrade']
    neg_words = ['down', 'fall', 'drop', 'loss', 'crash', 'miss', 'weak', 'bearish', 'decline', 'plunge', 'low', 'decrease', 'negative', 'fail', 'downgrade', 'warning', 'risk']
    score, total = 0, 0
    for item in news_list[:5]:
        title = item.get('title', '').lower()
        total += 1
        for w in pos_words:
            if w in title: score += 1
        for w in neg_words:
            if w in title: score -= 1
    normalized = max(0, min(100, 50 + (score / max(total, 1)) * 20))
    if normalized >= 65: return normalized, "إيجابي جداً 🟢"
    elif normalized >= 55: return normalized, "إيجابي "
    elif normalized <= 35: return normalized, "سلبي جداً 🔴"
    elif normalized <= 45: return normalized, "سلبي 🟥"
    return normalized, "محايد 🟡"

def get_analysis_data(ticker, tf):
    try:
        tf_map = {"5 دقائق": ("1d", "5m"), "15 دقيقة": ("7d", "15m"), "30 دقيقة": ("7d", "30m"), "1 ساعة": ("7d", "1h"), "4 ساعات": ("60d", "4h"), "يومي": ("2y", "1d"), "أسبوعي": ("5y", "1wk"), "شهري": ("10y", "1mo")}
        period, interval = tf_map.get(tf, ("2y", "1d"))
        data = yf.Ticker(ticker)
        df = data.history(period=period, interval=interval)
        if df.empty or len(df) < 20: return None, None
        
        current_price = float(df['Close'].iloc[-1])
        window = 20 if "دقيقة" in tf or "ساعة" in tf else 20
        support = float(df['Low'].rolling(window=window).min().iloc[-1])
        resistance = float(df['High'].rolling(window=window).max().iloc[-1])
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        current_rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        current_atr = float(tr.rolling(14).mean().iloc[-1])
        
        avg_volume = float(df['Volume'].rolling(window=20).mean().iloc[-1]) if 'Volume' in df.columns else 0
        current_volume = float(df['Volume'].iloc[-1]) if 'Volume' in df.columns and not df['Volume'].empty else 0
        volume_ratio = (current_volume / avg_volume) if avg_volume > 0 else 1.0
        
        return df, {'price': current_price, 'support': support, 'resistance': resistance, 'rsi': current_rsi, 'data': data, 'atr': current_atr, 'volume_ratio': volume_ratio}
    except: return None, None

# ==========================================
# 4. الشريط الجانبي
# ==========================================
st.sidebar.markdown("### 🌍 مركز التحكم")
selected_market = st.sidebar.selectbox("اختر السوق:", list(GLOBAL_MARKETS.keys()), index=list(GLOBAL_MARKETS.keys()).index(st.session_state.current_market))
if selected_market != st.session_state.current_market:
    st.session_state.current_market = selected_market
    st.session_state.watchlist = GLOBAL_MARKETS[selected_market].copy()
    st.session_state.selected_ticker = st.session_state.watchlist[0]
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📌 اختر سهم للتحليل")
st.session_state.selected_ticker = st.sidebar.radio("الأسهم المتاحة:", st.session_state.watchlist, index=st.session_state.watchlist.index(st.session_state.selected_ticker) if st.session_state.selected_ticker in st.session_state.watchlist else 0)

st.sidebar.markdown("---")
new_ticker = st.sidebar.text_input("أضف رمز مخصص:").strip().upper()
if st.sidebar.button("➕ إضافة"):
    if new_ticker and new_ticker not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_ticker)
        st.session_state.selected_ticker = new_ticker
        st.rerun()

time_frame = st.sidebar.selectbox("الإطار الزمني:", ["5 دقائق", "15 دقيقة", "30 دقيقة", "1 ساعة", "4 ساعات", "يومي", "أسبوعي", "شهري"], index=5)
dark_mode = st.sidebar.checkbox("الوضع الداكن", value=True)
theme_template = "plotly_dark" if dark_mode else "plotly_white"

# ==========================================
# 5. التبويبات الرئيسية
# ==========================================
st.markdown('<div class="main-header">🚀 منصة التداول الشاملة Ultimate</div>', unsafe_allow_html=True)
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "📊 التحليل الفني", "⚡ المضارب السريع", "💼 المحفظة", "🧮 حاسبة المخاطر", 
    " ربط المنصة", "🛡️ إدارة المخاطر", "🧠 الذكاء الاصطناعي", "⏳ Backtesting", "📋 الخيارات"
])

# ============ التبويب 1: التحليل الفني ============
with tab1:
    df, analysis = get_analysis_data(st.session_state.selected_ticker, time_frame)
    if df is None:
        st.warning(f"⚠️ لا توجد بيانات كافية لـ {st.session_state.selected_ticker}")
    else:
        company_info = get_company_info(st.session_state.selected_ticker)
        col_logo, col_info = st.columns([1, 4])
        with col_logo:
            if company_info['logo_url']:
                try:
                    response = requests.get(company_info['logo_url'], timeout=3)
                    if response.status_code == 200: st.image(Image.open(BytesIO(response.content)), width=70)
                except: st.markdown("### 📊")
            else: st.markdown("### 📊")
        with col_info:
            st.markdown(f"<div class='company-info'><h2 style='margin:0; color:white;'>{company_info['name']}</h2><p style='margin:5px 0; opacity:0.9;'>🏢 القطاع: {company_info['sector']} | الصناعة: {company_info['industry']}</p></div>", unsafe_allow_html=True)
        
        current_price, support, resistance, current_rsi, current_atr, volume_ratio = analysis['price'], analysis['support'], analysis['resistance'], analysis['rsi'], analysis['atr'], analysis['volume_ratio']
        dist_to_support = ((current_price - support) / current_price) * 100 if current_price != 0 else 0
        dist_to_resistance = ((resistance - current_price) / current_price) * 100 if current_price != 0 else 0
        
        signal_type, marker_color, marker_symbol, marker_size, signal_class = "مراقبة (Hold)", None, None, 0, "hold-signal"
        if dist_to_support <= 1.5 and current_rsi < 30: signal_type, marker_color, marker_symbol, marker_size, signal_class = "شراء قوية جداً ", "darkgreen", "square", 14, "buy-signal"
        elif dist_to_support <= 2.5 and current_rsi < 40: signal_type, marker_color, marker_symbol, marker_size, signal_class = "شراء مبدئية 📈", "lightgreen", "square", 10, "buy-signal"
        elif dist_to_resistance <= 1.5 and current_rsi > 70: signal_type, marker_color, marker_symbol, marker_size, signal_class = "بيع قوية جداً ⚠️", "darkred", "square", 14, "sell-signal"
        elif dist_to_resistance <= 2.5 and current_rsi > 60: signal_type, marker_color, marker_symbol, marker_size, signal_class = "بيع مبدئية 📉", "lightcoral", "square", 10, "sell-signal"
        
        st.markdown(f"### 📊 تحليل: {st.session_state.selected_ticker} <span class='live-indicator'></span>LIVE", unsafe_allow_html=True)
        col_a, col_b, col_c, col_d, col_e = st.columns(5)
        col_a.metric("💰 السعر", f"{current_price:.2f}")
        col_b.metric("🛡️ الدعم", f"{support:.2f}", delta=f"{dist_to_support:.1f}%")
        col_c.metric("🚧 المقاومة", f"{resistance:.2f}", delta=f"{dist_to_resistance:.1f}%")
        col_d.metric("📊 RSI", f"{current_rsi:.1f}")
        col_e.metric("📈 الحجم", f"{volume_ratio:.2f}x")
        
        if "شراء" in signal_type: st.markdown(f"<div class='signal-box {signal_class}'>🚨 تنبيه: {signal_type}</div>", unsafe_allow_html=True)
        elif "بيع" in signal_type: st.markdown(f"<div class='signal-box {signal_class}'>🚨 تنبيه: {signal_type}</div>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='signal-box {signal_class}'>ℹ️ الحالة: {signal_type}</div>", unsafe_allow_html=True)
        
        if volume_ratio >= st.session_state.risk_config.get('min_volume_ratio', 1.0):
            st.markdown(f"<div class='success-box'>✅ حجم التداول قوي ({volume_ratio:.2f}x) - الإشارة موثوقة</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='warning-box'>⚠️ تحذير: حجم التداول ضعيف ({volume_ratio:.2f}x) - الحركة مشبوهة!</div>", unsafe_allow_html=True)
        
        if current_atr > 0:
            atr_mult = 2.0
            sl_buy, tp_buy = current_price - (current_atr * atr_mult), current_price + (current_atr * atr_mult * 2)
            col_sl1, col_sl2, col_sl3 = st.columns(3)
            col_sl1.metric("📊 ATR", f"{current_atr:.2f}")
            col_sl2.metric(" وقف الخسارة", f"{sl_buy:.2f}")
            col_sl3.metric("🎯 الهدف", f"{tp_buy:.2f}")
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='السعر'))
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(50).mean(), name='SMA 50', line=dict(color='yellow', width=1)))
        bb_mid = df['Close'].rolling(20).mean()
        bb_std = df['Close'].rolling(20).std()
        fig.add_trace(go.Scatter(x=df.index, y=bb_mid + (bb_std * 2), name='Bollinger Upper', line=dict(color='orange', dash='dash'), opacity=0.5))
        fig.add_trace(go.Scatter(x=df.index, y=bb_mid - (bb_std * 2), name='Bollinger Lower', line=dict(color='orange', dash='dash'), opacity=0.5))
        fig.add_hline(y=support, line_dash="dot", line_color="green", annotation_text="دعم")
        fig.add_hline(y=resistance, line_dash="dot", line_color="red", annotation_text="مقاومة")
        if current_atr > 0:
            fig.add_hline(y=sl_buy, line_dash="dash", line_color="red", annotation_text=f"SL: {sl_buy:.2f}", opacity=0.7)
            fig.add_hline(y=tp_buy, line_dash="dash", line_color="green", annotation_text=f"TP: {tp_buy:.2f}", opacity=0.7)
        if marker_color:
            fig.add_trace(go.Scatter(x=[df.index[-1]], y=[current_price], mode='markers', marker=dict(color=marker_color, size=marker_size, symbol=marker_symbol, line=dict(width=2, color='white')), name=signal_type))
        fig.update_layout(title='رسم بياني تفاعلي', yaxis_title='السعر', xaxis_title='التاريخ', template=theme_template, height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("#### 🧠 تحليل مشاعر الأخبار:")
        try:
            news = analysis['data'].news
            sentiment_score, sentiment_label = analyze_sentiment(news)
            col_s1, col_s2 = st.columns(2)
            col_s1.metric("مؤشر المشاعر", f"{sentiment_score:.0f}/100")
            col_s2.markdown(f"**التصنيف:** {sentiment_label}")
        except: st.info("ℹ️ الأخبار غير متاحة.")

# ============ التبويب 2: المضارب السريع ============
with tab2:
    st.markdown("##  وضع المضارب السريع")
    st_autorefresh(interval=5000, limit=None, key="scalping_refresh")
    st.markdown("### 🔍 فحص سريع:")
    scalping_results = []
    for ticker in st.session_state.watchlist:
        df_s, analysis_s = get_analysis_data(ticker, "5 دقائق")
        if df_s is not None:
            price_s, rsi_s, support_s, resistance_s, vol_s = analysis_s['price'], analysis_s['rsi'], analysis_s['support'], analysis_s['resistance'], analysis_s['volume_ratio']
            dist_sup = ((price_s - support_s) / price_s) * 100 if price_s != 0 else 0
            dist_res = ((resistance_s - price_s) / price_s) * 100 if price_s != 0 else 0
            signal = "مراقبة"
            if dist_sup <= 1.5 and rsi_s < 30: signal = "🟢 شراء قوية"
            elif dist_res <= 1.5 and rsi_s > 70: signal = "🔴 بيع قوية"
            scalping_results.append({'ticker': ticker, 'price': price_s, 'rsi': rsi_s, 'signal': signal, 'volume': f"{vol_s:.2f}x"})
    if scalping_results:
        st.dataframe(pd.DataFrame(scalping_results), use_container_width=True)
    else: st.warning("⚠️ لا توجد بيانات كافية.")

# ============ التبويب 3: المحفظة ============
with tab3:
    st.markdown("## 💼 محفظة التداول")
    st.markdown(f"💰 الرصيد: **${st.session_state.portfolio['balance']:,.2f}**")
    col_add1, col_add2, col_add3, col_add4, col_add5 = st.columns(5)
    with col_add1: trade_ticker = st.text_input("الرمز", value=st.session_state.selected_ticker)
    with col_add2: trade_type = st.selectbox("النوع", ["شراء", "بيع"])
    with col_add3: trade_qty = st.number_input("الكمية", min_value=0.01, value=1.0)
    with col_add4: trade_price = st.number_input("سعر الدخول", min_value=0.01, value=100.0)
    with col_add5: trade_exit_price = st.number_input("سعر الخروج (0 للمفتوحة)", min_value=0.0, value=0.0)
    
    if st.button("➕ تسجيل الصفقة", use_container_width=True):
        result, profit_loss = None, 0
        if trade_exit_price > 0:
            profit_loss = (trade_exit_price - trade_price) * trade_qty if trade_type == "شراء" else (trade_price - trade_exit_price) * trade_qty
            result = "profit" if profit_loss > 0 else "loss"
            st.session_state.portfolio['balance'] += profit_loss
            if profit_loss < 0: st.session_state.portfolio['daily_loss'] += abs(profit_loss)
        st.session_state.portfolio['trades'].append({'ticker': trade_ticker, 'type': trade_type, 'qty': trade_qty, 'entry': trade_price, 'exit': trade_exit_price, 'pnl': profit_loss, 'result': result, 'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})
        save_json(PORTFOLIO_FILE, st.session_state.portfolio)
        st.success("✅ تم التسجيل!")
        st.rerun()
    
    if st.session_state.portfolio['trades']:
        st.dataframe(pd.DataFrame(st.session_state.portfolio['trades']), use_container_width=True)
        if st.button("🗑️ مسح السجل"):
            st.session_state.portfolio['trades'] = []
            save_json(PORTFOLIO_FILE, st.session_state.portfolio)
            st.rerun()

# ============ التبويب 4: حاسبة المخاطر ============
with tab4:
    st.markdown("## 🧮 حاسبة المخاطر")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        capital = st.number_input("رأس المال ($)", min_value=100, value=10000)
        risk_pct = st.slider("نسبة المخاطرة (%)", 0.5, 5.0, 2.0)
    with col_c2:
        entry = st.number_input("سعر الدخول", min_value=0.01, value=100.0)
        sl = st.number_input("وقف الخسارة", min_value=0.01, value=95.0)
    
    risk_amount = capital * (risk_pct / 100)
    risk_per_share = abs(entry - sl)
    if risk_per_share > 0:
        pos_size = risk_amount / risk_per_share
        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("مبلغ المخاطرة", f"${risk_amount:,.2f}")
        col_r2.metric("حجم المركز", f"{pos_size:.2f} سهم")
        col_r3.metric("إجمالي الاستثمار", f"${pos_size * entry:,.2f}")

# ============ التبويب 5: ربط المنصة ============
with tab5:
    st.markdown("## 🤖 التداول التجريبي (Alpaca)")
    col_api1, col_api2 = st.columns(2)
    with col_api1: api_key = st.text_input("API Key", type="password")
    with col_api2: api_secret = st.text_input("Secret Key", type="password")
    if st.button("💾 حفظ والاتصال"):
        if api_key and api_secret:
            st.session_state.alpaca_api_key = api_key
            st.session_state.alpaca_secret_key = api_secret
            st.rerun()
    
    if st.session_state.get('alpaca_api_key'):
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            client = TradingClient(api_key=st.session_state.alpaca_api_key, secret_key=st.session_state.alpaca_secret_key, paper=True)
            account = client.get_account()
            col_acc1, col_acc2 = st.columns(2)
            col_acc1.metric("القيمة الكلية", f"${float(account.portfolio_value):,.2f}")
            col_acc2.metric("النقد المتاح", f"${float(account.cash):,.2f}")
            
            st.markdown("### ⚡ تنفيذ صفقة:")
            col_e1, col_e2, col_e3 = st.columns(3)
            with col_e1: exec_ticker = st.text_input("الرمز", value="AAPL")
            with col_e2: exec_qty = st.number_input("الكمية", min_value=1.0, value=1.0)
            with col_e3: exec_side = st.selectbox("النوع", ["BUY", "SELL"])
            if st.button(" تنفيذ"):
                order = client.submit_order(MarketOrderRequest(symbol=exec_ticker.upper(), qty=exec_qty, side=OrderSide.BUY if exec_side=="BUY" else OrderSide.SELL, time_in_force=TimeInForce.DAY))
                st.success(f"✅ تم! رقم: {order.id}")
        except Exception as e: st.error(f"خطأ: {e}")

# ============ التبويب 6: إدارة المخاطر ============
with tab6:
    st.markdown("## ️ إعدادات إدارة المخاطر")
    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1: daily_limit = st.number_input("حد الخسارة اليومي (%)", 0.5, 10.0, st.session_state.risk_config['daily_loss_limit'])
    with col_r2: max_losses = st.number_input("الحد الأقصى للخسائر المتتالية", 2, 10, st.session_state.risk_config['max_consecutive_losses'])
    with col_r3: min_vol = st.number_input("الحد الأدنى للحجم (x)", 0.5, 3.0, st.session_state.risk_config['min_volume_ratio'])
    if st.button("💾 حفظ"):
        st.session_state.risk_config = {'daily_loss_limit': daily_limit, 'max_consecutive_losses': max_losses, 'min_volume_ratio': min_vol}
        save_json(RISK_CONFIG_FILE, st.session_state.risk_config)
        st.success("✅ تم الحفظ!")

# ============ التبويب 7: الذكاء الاصطناعي ============
with tab7:
    st.markdown("##  الذكاء الاصطناعي (XGBoost)")
    df_ml, analysis_ml = get_analysis_data(st.session_state.selected_ticker, time_frame)
    if df_ml is not None and len(df_ml) > 50:
        try:
            df_ml['RSI'] = 100 - (100 / (1 + (df_ml['Close'].diff().where(df_ml['Close'].diff() > 0, 0).rolling(14).mean() / (-df_ml['Close'].diff().where(df_ml['Close'].diff() < 0, 0).rolling(14).mean()))))
            df_ml['MACD'] = df_ml['Close'].ewm(span=12).mean() - df_ml['Close'].ewm(span=26).mean()
            df_ml['Target'] = (df_ml['Close'].shift(-1) > df_ml['Close']).astype(int)
            df_ml = df_ml.dropna()
            feature_cols = ['RSI', 'MACD']
            X, y = df_ml[feature_cols], df_ml['Target']
            split_idx = int(len(X) * 0.8)
            model = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.1, use_label_encoder=False, eval_metric='logloss')
            model.fit(X[:split_idx], y[:split_idx])
            pred = model.predict(X.iloc[-1:].values)[0]
            prob = model.predict_proba(X.iloc[-1:].values)[0]
            acc = model.score(X[split_idx:], y[split_idx:])
            
            col_p1, col_p2, col_p3 = st.columns(3)
            col_p1.metric("التنبؤ", " صعود" if pred == 1 else " هبوط")
            col_p2.metric("دقة النموذج", f"{acc*100:.1f}%")
            col_p3.metric("احتمالية الصعود", f"{prob[1]*100:.1f}%")
        except Exception as e: st.error(f"خطأ في ML: {e}")
    else: st.warning("بيانات غير كافية للذكاء الاصطناعي.")

# ============ التبويب 8: Backtesting ============
with tab8:
    st.markdown("## ⏳ اختبار الماضي (Backtesting)")
    col_bt1, col_bt2 = st.columns(2)
    with col_bt1: bt_ticker = st.text_input("الرمز", value="AAPL")
    with col_bt2: bt_years = st.slider("عدد السنوات", 1, 5, 3)
    bt_cash = st.number_input("رأس المال الابتدائي", min_value=1000, value=10000)
    bt_rsi_buy = st.slider("RSI للشراء أقل من", 20, 50, 35)
    bt_rsi_sell = st.slider("RSI للبيع أعلى من", 50, 80, 65)
    
    if st.button("🚀 بدء الاختبار"):
        df_bt = yf.Ticker(bt_ticker).history(period=f"{bt_years}y")
        if not df_bt.empty:
            delta = df_bt['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df_bt['RSI'] = 100 - (100 / (1 + gain / loss))
            
            cash, holdings, equity_curve = bt_cash, 0, []
            for i in range(50, len(df_bt)):
                price = df_bt['Close'].iloc[i]
                rsi = df_bt['RSI'].iloc[i]
                if holdings == 0 and rsi < bt_rsi_buy:
                    holdings = cash / price
                    cash = 0
                elif holdings > 0 and rsi > bt_rsi_sell:
                    cash = holdings * price
                    holdings = 0
                equity_curve.append(cash + (holdings * price))
            
            final_val = equity_curve[-1] if equity_curve else bt_cash
            profit = final_val - bt_cash
            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("القيمة النهائية", f"${final_val:,.2f}")
            col_r2.metric("الربح/الخسارة", f"${profit:,.2f}", delta=f"{(profit/bt_cash)*100:.2f}%")
            col_r3.metric("عدد الصفقات", len([i for i in range(50, len(df_bt)) if df_bt['RSI'].iloc[i] < bt_rsi_buy or df_bt['RSI'].iloc[i] > bt_rsi_sell]) // 2)
            
            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(x=df_bt.index[50:], y=equity_curve, mode='lines', name='نمو المحفظة', line=dict(color='green')))
            fig_bt.update_layout(title='منحنى نمو المحفظة', template=theme_template, height=400)
            st.plotly_chart(fig_bt, use_container_width=True)
        else: st.error("لا توجد بيانات.")

# ============ التبويب 9: الخيارات ============
with tab9:
    st.markdown("## 📋 الخيارات (Options Chain)")
    opt_ticker = st.text_input("رمز السهم الأمريكي", value="AAPL").upper()
    if st.button("🔍 جلب الخيارات"):
        try:
            expirations = yf.Ticker(opt_ticker).options
            if expirations:
                sel_date = st.selectbox("تاريخ الانتهاء", expirations)
                chain = yf.Ticker(opt_ticker).option_chain(sel_date)
                col_c, col_p = st.columns(2)
                with col_c:
                    st.markdown("### 🟢 Calls")
                    st.dataframe(chain.calls[['strike', 'lastPrice', 'volume', 'openInterest']], use_container_width=True)
                with col_p:
                    st.markdown("### 🔴 Puts")
                    st.dataframe(chain.puts[['strike', 'lastPrice', 'volume', 'openInterest']], use_container_width=True)
            else: st.info("لا توجد خيارات.")
        except Exception as e: st.error(f"خطأ: {e}")
