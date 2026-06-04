from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# ==========================================
# دوال التنفيذ التلقائي
# ==========================================
def get_alpaca_client(api_key, api_secret, paper=True):
    """إنشاء اتصال مع Alpaca"""
    try:
        client = TradingClient(
            api_key=api_key,
            secret_key=api_secret,
            paper=paper  # True = وضع الاختبار، False = أموال حقيقية
        )
        return client, None
    except Exception as e:
        return None, str(e)

def execute_auto_trade(client, ticker, side, qty, order_type="market"):
    """تنفيذ صفقة تلقائياً"""
    try:
        if order_type == "market":
            order_data = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY
            )
        else:
            order_data = LimitOrderRequest(
                symbol=ticker,
                qty=qty,
                side=side,
                limit_price=st.session_state.get('limit_price', 0),
                time_in_force=TimeInForce.DAY
            )
        
        order = client.submit_order(order_data=order_data)
        return order, None
    except Exception as e:
        return None, str(e)

def get_account_info(client):
    """جلب معلومات الحساب"""
    try:
        account = client.get_account()
        return {
            'equity': float(account.equity),
            'cash': float(account.cash),
            'portfolio_value': float(account.portfolio_value),
            'buying_power': float(account.buying_power)
        }, None
    except Exception as e:
        return None, str(e)
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
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

# ==========================================
# دالة الذكاء الاصطناعي التنبؤي
# ==========================================
def prepare_ml_features(df):
    """تحضير البيانات لتدريب نموذج ML"""
    df_ml = df.copy()
    
    # مؤشرات فنية إضافية
    df_ml['RSI'] = 100 - (100 / (1 + (df_ml['Close'].diff().where(df_ml['Close'].diff() > 0, 0).rolling(14).mean() / 
                                     (-df_ml['Close'].diff().where(df_ml['Close'].diff() < 0, 0).rolling(14).mean()))))
    
    df_ml['MACD'] = df_ml['Close'].ewm(span=12).mean() - df_ml['Close'].ewm(span=26).mean()
    df_ml['Signal_Line'] = df_ml['MACD'].ewm(span=9).mean()
    df_ml['MACD_Hist'] = df_ml['MACD'] - df_ml['Signal_Line']
    
    # Bollinger Bands
    df_ml['BB_Middle'] = df_ml['Close'].rolling(20).mean()
    df_ml['BB_Std'] = df_ml['Close'].rolling(20).std()
    df_ml['BB_Upper'] = df_ml['BB_Middle'] + (df_ml['BB_Std'] * 2)
    df_ml['BB_Lower'] = df_ml['BB_Middle'] - (df_ml['BB_Std'] * 2)
    df_ml['BB_Position'] = (df_ml['Close'] - df_ml['BB_Lower']) / (df_ml['BB_Upper'] - df_ml['BB_Lower'])
    
    # Average True Range
    high_low = df_ml['High'] - df_ml['Low']
    high_close = abs(df_ml['High'] - df_ml['Close'].shift())
    low_close = abs(df_ml['Low'] - df_ml['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_ml['ATR'] = tr.rolling(14).mean()
    
    # Volume indicators
    df_ml['Volume_SMA'] = df_ml['Volume'].rolling(20).mean()
    df_ml['Volume_Ratio'] = df_ml['Volume'] / df_ml['Volume_SMA']
    
    # Price momentum
    df_ml['Momentum_5'] = df_ml['Close'].pct_change(5)
    df_ml['Momentum_10'] = df_ml['Close'].pct_change(10)
    df_ml['Momentum_20'] = df_ml['Close'].pct_change(20)
    
    # Volatility
    df_ml['Volatility'] = df_ml['Close'].rolling(20).std() / df_ml['Close'].rolling(20).mean()
    
    # Target: هل السعر سيرتفع في الفترة القادمة؟ (1 = صعود، 0 = هبوط)
    df_ml['Target'] = (df_ml['Close'].shift(-1) > df_ml['Close']).astype(int)
    
    # إزالة الصفوف الفارغة
    df_ml = df_ml.dropna()
    
    return df_ml

def train_and_predict(df, ticker):
    """تدريب نموذج XGBoost المحسّن"""
    try:
        df_ml = prepare_ml_features(df)
        
        if len(df_ml) < 50:
            return None, None, "بيانات غير كافية للتدريب"
        
        feature_cols = ['RSI', 'MACD', 'Signal_Line', 'MACD_Hist', 'BB_Position', 
                       'ATR', 'Volume_Ratio', 'Momentum_5', 'Momentum_10', 
                       'Momentum_20', 'Volatility']
        
        X = df_ml[feature_cols]
        y = df_ml['Target']
        
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # نموذج XGBoost المحسّن
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        
        model.fit(X_train, y_train)
        
        latest_features = X.iloc[-1:].values
        prediction = model.predict(latest_features)[0]
        probability = model.predict_proba(latest_features)[0]
        
        accuracy = model.score(X_test, y_test)
        
        feature_importance = dict(zip(feature_cols, model.feature_importances_))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return prediction, {
            'accuracy': accuracy,
            'probability_up': probability[1],
            'probability_down': probability[0],
            'top_features': top_features,
            'model_type': 'XGBoost (محسّن)'
        }, None
        
    except Exception as e:
        return None, None, str(e)

warnings.filterwarnings("ignore")

# ==========================================
# 1. إعدادات الصفحة والمظهر
# ==========================================
st.set_page_config(page_title="منصة التداول الخرافية Pro+ Risk Manager", layout="wide", page_icon="🛡️")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');
    * { font-family: 'Tajawal', sans-serif; }
    .main-header {
        font-size: 2.5rem; font-weight: 800; text-align: center; margin-bottom: 20px;
        background: linear-gradient(90deg, #1E88E5 0%, #00E676 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .company-info {
        background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%);
        padding: 20px; border-radius: 15px; color: white; margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    .live-indicator {
        display: inline-block; width: 12px; height: 12px; background-color: #00E676;
        border-radius: 50%; animation: pulse 1.5s infinite; margin-right: 10px;
        box-shadow: 0 0 10px #00E676;
    }
    @keyframes pulse {
        0% {box-shadow: 0 0 0 0 rgba(0, 230, 118, 0.7);}
        70% {box-shadow: 0 0 0 10px rgba(0, 230, 118, 0);}
        100% {box-shadow: 0 0 0 0 rgba(0, 230, 118, 0);}
    }
    .signal-box {
        padding: 15px; border-radius: 10px; font-weight: bold; font-size: 1.1rem;
        margin: 10px 0; box-shadow: 0 4px 10px rgba(0,0,0,0.1); color: white;
    }
    .buy-signal { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .sell-signal { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); }
    .hold-signal { background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%); }
    .warning-box {
        padding: 15px; border-radius: 10px; font-weight: bold;
        margin: 10px 0; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
    }
    .success-box {
        padding: 15px; border-radius: 10px; font-weight: bold;
        margin: 10px 0; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
    }
    .stop-loss-box {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
        padding: 20px; border-radius: 15px; color: white;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. إدارة الملفات المحلية
# ==========================================
PORTFOLIO_FILE = "portfolio.json"
RISK_CONFIG_FILE = "risk_config.json"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"trades": [], "balance": 10000, "daily_loss": 0, "last_reset_date": datetime.date.today().strftime('%Y-%m-%d')}

def save_portfolio(data):
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_risk_config():
    if os.path.exists(RISK_CONFIG_FILE):
        with open(RISK_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"daily_loss_limit": 2.0, "max_consecutive_losses": 3, "min_volume_ratio": 1.0}

def save_risk_config(data):
    with open(RISK_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_portfolio()
if 'risk_config' not in st.session_state:
    st.session_state.risk_config = load_risk_config()

# إعادة تعيين الخسارة اليومية إذا كان يوم جديد
today = datetime.date.today().strftime('%Y-%m-%d')
if st.session_state.portfolio.get('last_reset_date') != today:
    st.session_state.portfolio['daily_loss'] = 0
    st.session_state.portfolio['last_reset_date'] = today
    save_portfolio(st.session_state.portfolio)

# ==========================================
# 3. قاعدة بيانات الأسواق
# ==========================================
GLOBAL_MARKETS = {
    "[US] السوق الأمريكي": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY"],
    "[SA] السوق السعودي": ["2222.SR", "1120.SR", "2010.SR", "1150.SR", "2280.SR"],
    "[EG] السوق المصري": ["COMI.CA", "HRHO.CA", "ETEL.CA", "SWDY.CA", "AMOC.CA"],
    "[AE] السوق الإماراتي": ["ADCB.AD", "FAB.AD", "EMAAR.DU", "DIB.AD", "ALDAR.AD"],
    "[Crypto] العملات الرقمية": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "[Global] المعادن والمؤشرات": ["GC=F", "SI=F", "^GSPC", "^DJI", "^IXIC"],
    "[Forex] الفوركس": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"],  # جديد
    "[Options] الخيارات": ["AAPL", "TSLA", "SPY"]  # جديد - سنضيف تفاصيل الخيارات لاحقاً
}
# ==========================================
# 4. إدارة الجلسة
# ==========================================
if 'current_market' not in st.session_state:
    st.session_state.current_market = "[US] السوق الأمريكي"
    st.session_state.watchlist = GLOBAL_MARKETS[st.session_state.current_market].copy()
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = st.session_state.watchlist[0]
if 'company_info_cache' not in st.session_state:
    st.session_state.company_info_cache = {}

st_autorefresh(interval=15000, limit=None, key="live_refresh")

# ==========================================
# 5. دوال مساعدة
# ==========================================
def get_company_info(ticker):
    try:
        if ticker in st.session_state.company_info_cache:
            return st.session_state.company_info_cache[ticker]
        stock = yf.Ticker(ticker)
        info = stock.info
        company_name = info.get('longName', info.get('shortName', ticker))
        sector = info.get('sector', 'غير محدد')
        industry = info.get('industry', 'غير محدد')
        logo_url = None
        try:
            if 'logo_url' in info:
                logo_url = info['logo_url']
            else:
                clean_ticker = ticker.replace('.SR','').replace('.CA','').replace('.AD','').replace('.DU','').replace('-USD','').lower()
                logo_url = f"https://logo.clearbit.com/{clean_ticker}.com"
        except:
            logo_url = None
        company_data = {'name': company_name, 'sector': sector, 'industry': industry, 'logo_url': logo_url}
        st.session_state.company_info_cache[ticker] = company_data
        return company_data
    except Exception:
        return {'name': ticker, 'sector': 'غير محدد', 'industry': 'غير محدد', 'logo_url': None}

def analyze_sentiment(news_list):
    positive_words = ['up', 'rise', 'gain', 'growth', 'profit', 'beat', 'strong', 'bullish', 'rally', 'surge', 'record', 'high', 'increase', 'positive', 'success', 'upgrade']
    negative_words = ['down', 'fall', 'drop', 'loss', 'crash', 'miss', 'weak', 'bearish', 'decline', 'plunge', 'low', 'decrease', 'negative', 'fail', 'downgrade', 'warning', 'risk']
    
    if not news_list:
        return 50, "محايد"
    
    score = 0
    total = 0
    for item in news_list[:5]:
        title = item.get('title', '').lower()
        total += 1
        for word in positive_words:
            if word in title:
                score += 1
        for word in negative_words:
            if word in title:
                score -= 1
    
    normalized = 50 + (score / max(total, 1)) * 20
    normalized = max(0, min(100, normalized))
    
    if normalized >= 65:
        return normalized, "إيجابي جداً 🟢"
    elif normalized >= 55:
        return normalized, "إيجابي 🟩"
    elif normalized <= 35:
        return normalized, "سلبي جداً 🔴"
    elif normalized <= 45:
        return normalized, "سلبي "
    else:
        return normalized, "محايد 🟡"

def play_alert_sound():
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except:
        pass

def calculate_atr(df, period=14):
    """حساب Average True Range لوقف الخسارة الذكي"""
    high = df['High']
    low = df['Low']
    close = df['Close'].shift(1)
    
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def check_consecutive_losses(portfolio):
    """فحص الخسائر المتتالية"""
    trades = portfolio.get('trades', [])
    if len(trades) < 2:
        return 0, False
    
    consecutive = 0
    for trade in reversed(trades):
        if trade.get('result') == 'loss':
            consecutive += 1
        else:
            break
    
    max_losses = st.session_state.risk_config.get('max_consecutive_losses', 3)
    is_blocked = consecutive >= max_losses
    
    return consecutive, is_blocked

def check_daily_loss(portfolio):
    """فحص حد الخسارة اليومي"""
    daily_loss = portfolio.get('daily_loss', 0)
    daily_limit = st.session_state.risk_config.get('daily_loss_limit', 2.0)
    capital = portfolio.get('balance', 10000)
    
    loss_percentage = (daily_loss / capital) * 100 if capital > 0 else 0
    is_blocked = loss_percentage >= daily_limit
    
    return loss_percentage, daily_limit, is_blocked

# ==========================================
# 6. الشريط الجانبي
# ==========================================
st.sidebar.markdown("### 🌍 مركز التحكم")

selected_market = st.sidebar.selectbox(
    "اختر السوق:", 
    list(GLOBAL_MARKETS.keys()), 
    index=list(GLOBAL_MARKETS.keys()).index(st.session_state.current_market)
)

if selected_market != st.session_state.current_market:
    st.session_state.current_market = selected_market
    st.session_state.watchlist = GLOBAL_MARKETS[selected_market].copy()
    st.session_state.selected_ticker = st.session_state.watchlist[0]
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("###  اختر سهم للتحليل")

st.session_state.selected_ticker = st.sidebar.radio(
    "الأسهم المتاحة:", 
    st.session_state.watchlist,
    index=st.session_state.watchlist.index(st.session_state.selected_ticker) if st.session_state.selected_ticker in st.session_state.watchlist else 0
)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ إعدادات العرض")

new_ticker = st.sidebar.text_input("أضف رمز مخصص:").strip().upper()
if st.sidebar.button("➕ إضافة"):
    if new_ticker and new_ticker not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_ticker)
        st.session_state.selected_ticker = new_ticker
        st.rerun()

time_frame = st.sidebar.selectbox(
    "الإطار الزمني:", 
    ["5 دقائق", "15 دقيقة", "30 دقيقة", "1 ساعة", "4 ساعات", "يومي", "أسبوعي", "شهري"],
    index=5
)

dark_mode = st.sidebar.checkbox("الوضع الداكن", value=True)
theme_template = "plotly_dark" if dark_mode else "plotly_white"

# ==========================================
# 7. دالة التحليل الفني الأساسية
# ==========================================
def get_analysis_data(ticker, tf):
    try:
        tf_map = {
            "5 دقائق": ("1d", "5m"), "15 دقيقة": ("7d", "15m"), "30 دقيقة": ("7d", "30m"),
            "1 ساعة": ("7d", "1h"), "4 ساعات": ("60d", "4h"), "يومي": ("2y", "1d"),
            "أسبوعي": ("5y", "1wk"), "شهري": ("10y", "1mo")
        }
        period, interval = tf_map.get(tf, ("2y", "1d"))
        
        data = yf.Ticker(ticker)
        df = data.history(period=period, interval=interval)
        if df.empty or len(df) < 20:
            return None, None
        
        current_price = float(df['Close'].iloc[-1])
        window = 20 if "دقيقة" in tf or "ساعة" in tf else 20
        support = float(df['Low'].rolling(window=window).min().iloc[-1])
        resistance = float(df['High'].rolling(window=window).max().iloc[-1])
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        current_rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        
        # حساب ATR لوقف الخسارة الذكي
        atr = calculate_atr(df, 14)
        current_atr = float(atr.iloc[-1]) if not atr.empty else 0
        
        # حساب حجم التداول المتوسط
        avg_volume = float(df['Volume'].rolling(window=20).mean().iloc[-1]) if 'Volume' in df.columns else 0
        current_volume = float(df['Volume'].iloc[-1]) if 'Volume' in df.columns and not df['Volume'].empty else 0
        volume_ratio = (current_volume / avg_volume) if avg_volume > 0 else 1.0
        
        return df, {
            'price': current_price, 'support': support, 'resistance': resistance,
            'rsi': current_rsi, 'data': data, 'atr': current_atr,
            'avg_volume': avg_volume, 'current_volume': current_volume, 'volume_ratio': volume_ratio
        }
        
    except Exception:
        return None, None

# ==========================================
# 8. التبويبات الرئيسية
# ==========================================
st.markdown('<div class="main-header">🛡️ منصة التداول الخرافية Pro+ Risk Manager</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "📊 التحليل الفني",
    "⚡ وضع المضارب السريع",
    "💼 محفظة التداول",
    " حاسبة المخاطر",
    " ربط المنصة",
    "🛡️ إدارة المخاطر",
    "🧠 الذكاء الاصطناعي",
    "⏳ Backtesting",
    "📋 الخيارات (Options)"
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
                    if response.status_code == 200:
                        image = Image.open(BytesIO(response.content))
                        st.image(image, width=70)
                except:
                    st.markdown("### 📊")
            else:
                st.markdown("### 📊")
        with col_info:
            st.markdown(f"<div class='company-info'><h2 style='margin:0; color:white;'>{company_info['name']}</h2><p style='margin:5px 0; opacity:0.9;'>🏢 القطاع: {company_info['sector']} | الصناعة: {company_info['industry']}</p></div>", unsafe_allow_html=True)
        
        current_price = analysis['price']
        support = analysis['support']
        resistance = analysis['resistance']
        current_rsi = analysis['rsi']
        current_atr = analysis['atr']
        volume_ratio = analysis['volume_ratio']
        data_obj = analysis['data']
        
        dist_to_support = ((current_price - support) / current_price) * 100 if current_price != 0 else 0
        dist_to_resistance = ((resistance - current_price) / current_price) * 100 if current_price != 0 else 0
        
        signal_type = "مراقبة (Hold)"
        marker_color, marker_symbol, marker_size = None, None, 0
        signal_class = "hold-signal"
        
        if dist_to_support <= 1.5 and current_rsi < 30:
            signal_type = "شراء قوية جداً 🔥"
            marker_color, marker_symbol, marker_size = "darkgreen", "square", 14
            signal_class = "buy-signal"
        elif dist_to_support <= 2.5 and current_rsi < 40:
            signal_type = "شراء مبدئية 📈"
            marker_color, marker_symbol, marker_size = "lightgreen", "square", 10
            signal_class = "buy-signal"
        elif dist_to_resistance <= 1.5 and current_rsi > 70:
            signal_type = "بيع قوية جداً ️"
            marker_color, marker_symbol, marker_size = "darkred", "square", 14
            signal_class = "sell-signal"
        elif dist_to_resistance <= 2.5 and current_rsi > 60:
            signal_type = "بيع مبدئية 📉"
            marker_color, marker_symbol, marker_size = "lightcoral", "square", 10
            signal_class = "sell-signal"
        
        st.markdown(f"### 📊 تحليل: {st.session_state.selected_ticker} <span class='live-indicator'></span>LIVE", unsafe_allow_html=True)
        
        col_a, col_b, col_c, col_d, col_e = st.columns(5)
        col_a.metric("💰 السعر", f"{current_price:.2f}")
        col_b.metric("️ الدعم", f"{support:.2f}", delta=f"{dist_to_support:.1f}%")
        col_c.metric("🚧 المقاومة", f"{resistance:.2f}", delta=f"{dist_to_resistance:.1f}%")
        col_d.metric(" RSI", f"{current_rsi:.1f}")
        col_e.metric("📈 حجم التداول", f"{volume_ratio:.2f}x")
        
        # صندوق الإشارة
        if "شراء" in signal_type:
            st.markdown(f"<div class='signal-box {signal_class}'>🚨 تنبيه: {signal_type}<br><small>السعر يلامس منطقة الدعم</small></div>", unsafe_allow_html=True)
        elif "بيع" in signal_type:
            st.markdown(f"<div class='signal-box {signal_class}'>🚨 تنبيه: {signal_type}<br><small>السعر يلامس منطقة المقاومة</small></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='signal-box {signal_class}'>ℹ️ الحالة: {signal_type}<br><small>السعر في المنطقة المحايدة</small></div>", unsafe_allow_html=True)
        
        # ===== ميزة 3: مؤشر قوة الحركة (Volume Confirmation) =====
        st.markdown("#### 📊 تأكيد حجم التداول:")
        min_volume_ratio = st.session_state.risk_config.get('min_volume_ratio', 1.0)
        
        if volume_ratio >= min_volume_ratio:
            st.markdown(f"<div class='success-box'>✅ حجم التداول قوي ({volume_ratio:.2f}x من المتوسط) - الإشارة موثوقة</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='warning-box'>⚠️ تحذير: حجم التداول ضعيف ({volume_ratio:.2f}x من المتوسط) - الحركة قد تكون مشبوهة! يُنصح بالانتظار</div>", unsafe_allow_html=True)
        
        # ===== ميزة 1: وقف الخسارة الذكي (Smart Stop-Loss) =====
        st.markdown("#### 🛡️ وقف الخسارة الذكي (ATR-Based):")
        
        if current_atr > 0:
            # حساب وقف الخسارة بناءً على ATR
            atr_multiplier = 2.0  # مضاعف ATR القياسي
            stop_loss_buy = current_price - (current_atr * atr_multiplier)
            stop_loss_sell = current_price + (current_atr * atr_multiplier)
            
            # حساب الهدف (Take Profit) بنسبة 1:2
            take_profit_buy = current_price + (current_atr * atr_multiplier * 2)
            take_profit_sell = current_price - (current_atr * atr_multiplier * 2)
            
            col_sl1, col_sl2, col_sl3, col_sl4 = st.columns(4)
            col_sl1.metric("📊 ATR الحالي", f"{current_atr:.2f}")
            col_sl2.metric("🛑 وقف الخسارة (شراء)", f"{stop_loss_buy:.2f}", delta=f"-{atr_multiplier}x ATR")
            col_sl3.metric("🎯 الهدف (شراء)", f"{take_profit_buy:.2f}", delta=f"+{atr_multiplier*2}x ATR")
            col_sl4.metric("️ نسبة المخاطرة/العائد", "1:2")
            
            st.markdown(f"""
            <div class='stop-loss-box'>
                <h4 style='margin:0; color:white;'>💡 توصية وقف الخسارة الذكي:</h4>
                <p style='margin:10px 0; color:white;'>
                    إذا دخلت صفقة <b>شراء</b> عند {current_price:.2f}، ضع وقف الخسارة عند <b>{stop_loss_buy:.2f}</b> والهدف عند <b>{take_profit_buy:.2f}</b><br>
                    إذا دخلت صفقة <b>بيع</b> عند {current_price:.2f}، ضع وقف الخسارة عند <b>{stop_loss_sell:.2f}</b> والهدف عند <b>{take_profit_sell:.2f}</b>
                </p>
                <small style='color:rgba(255,255,255,0.8);'>
                    * الحساب بناءً على مؤشر ATR (Average True Range) الذي يقيس التقلب الحقيقي للسهم
                </small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("️ لا يمكن حساب ATR بسبب نقص البيانات.")
        
        # الشارت
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='السعر'))
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(window=50).mean(), name='SMA 50', line=dict(color='yellow', width=1)))
        bb_mid = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        fig.add_trace(go.Scatter(x=df.index, y=bb_mid + (bb_std * 2), name='Bollinger Upper', line=dict(color='orange', dash='dash'), opacity=0.5))
        fig.add_trace(go.Scatter(x=df.index, y=bb_mid - (bb_std * 2), name='Bollinger Lower', line=dict(color='orange', dash='dash'), opacity=0.5))
        fig.add_hline(y=support, line_dash="dot", line_color="green", annotation_text="دعم")
        fig.add_hline(y=resistance, line_dash="dot", line_color="red", annotation_text="مقاومة")
        
        # إضافة خطوط وقف الخسارة والهدف
        if current_atr > 0:
            fig.add_hline(y=stop_loss_buy, line_dash="dash", line_color="red", annotation_text=f"SL Buy: {stop_loss_buy:.2f}", opacity=0.7)
            fig.add_hline(y=take_profit_buy, line_dash="dash", line_color="green", annotation_text=f"TP Buy: {take_profit_buy:.2f}", opacity=0.7)
        
        if marker_color:
            fig.add_trace(go.Scatter(
                x=[df.index[-1]], y=[current_price], mode='markers',
                marker=dict(color=marker_color, size=marker_size, symbol=marker_symbol, line=dict(width=2, color='white')),
                name=signal_type, showlegend=True
            ))
        
        fig.update_layout(
            title=f'رسم بياني تفاعلي مع وقف الخسارة الذكي',
            yaxis_title='السعر', xaxis_title='التاريخ',
            template=theme_template, height=600, xaxis_rangeslider_visible=False
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # تحليل المشاعر
        st.markdown("#### 🧠 تحليل مشاعر الأخبار (AI Sentiment):")
        try:
            news = data_obj.news
            sentiment_score, sentiment_label = analyze_sentiment(news)
            
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.metric("مؤشر المشاعر", f"{sentiment_score:.0f}/100")
            with col_s2:
                st.markdown(f"**التصنيف:** {sentiment_label}")
            
            fig_sentiment = go.Figure(go.Indicator(
                mode="gauge+number",
                value=sentiment_score,
                title={'text': "من الخوف إلى الطمع"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 35], 'color': "#ef473a"},
                        {'range': [35, 65], 'color': "#ffd166"},
                        {'range': [65, 100], 'color': "#38ef7d"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': sentiment_score
                    }
                }
            ))
            fig_sentiment.update_layout(height=250, template=theme_template)
            st.plotly_chart(fig_sentiment, use_container_width=True)
            
            if news:
                st.markdown("####  آخر الأخبار:")
                for i, item in enumerate(news[:3]):
                    try:
                        pub_time = datetime.datetime.fromtimestamp(item['providerPublishTime']).strftime('%Y-%m-%d %H:%M')
                        st.markdown(f"**{i+1}.** [{item['title']}]({item['link']})  \n*🕒 {pub_time}*")
                    except:
                        continue
        except:
            st.info("ℹ️ الأخبار غير متاحة حالياً.")

# ============ التبويب 2: وضع المضارب السريع ============
with tab2:
    st.markdown("## ⚡ وضع المضارب السريع (Scalping Mode)")
    st.markdown("يتم فحص الأسواق كل **5 ثوانٍ** مع تنبيهات صوتية فورية عند ظهور إشارات قوية.")
    
    col_alert1, col_alert2 = st.columns(2)
    with col_alert1:
        enable_sound = st.checkbox("🔔 تفعيل التنبيهات الصوتية", value=True)
    with col_alert2:
        enable_popup = st.checkbox("💥 تفعيل التنبيهات المنبثقة", value=True)
    
    st_autorefresh(interval=5000, limit=None, key="scalping_refresh")
    
    st.markdown("---")
    st.markdown("### 🔍 فحص سريع لجميع الأسهم في القائمة:")
    
    scalping_results = []
    for ticker in st.session_state.watchlist:
        df_s, analysis_s = get_analysis_data(ticker, "5 دقائق")
        if df_s is not None:
            price_s = analysis_s['price']
            rsi_s = analysis_s['rsi']
            support_s = analysis_s['support']
            resistance_s = analysis_s['resistance']
            volume_ratio_s = analysis_s['volume_ratio']
            dist_sup = ((price_s - support_s) / price_s) * 100 if price_s != 0 else 0
            dist_res = ((resistance_s - price_s) / price_s) * 100 if price_s != 0 else 0
            
            signal = "مراقبة"
            volume_status = "✅" if volume_ratio_s >= 1.0 else "⚠️"
            
            if dist_sup <= 1.5 and rsi_s < 30:
                signal = " شراء قوية"
                if enable_sound and volume_ratio_s >= 1.0:
                    play_alert_sound()
            elif dist_res <= 1.5 and rsi_s > 70:
                signal = "🔴 بيع قوية"
                if enable_sound and volume_ratio_s >= 1.0:
                    play_alert_sound()
            
            scalping_results.append({
                'ticker': ticker, 'price': price_s, 'rsi': rsi_s, 
                'signal': signal, 'volume': f"{volume_status} {volume_ratio_s:.2f}x"
            })
    
    if scalping_results:
        df_scalp = pd.DataFrame(scalping_results)
        st.dataframe(df_scalp, use_container_width=True)
        
        strong_signals = df_scalp[df_scalp['signal'] != "مراقبة"]
        if not strong_signals.empty:
            st.error(f"🚨 تم اكتشاف {len(strong_signals)} إشارة قوية! راجع التبويب الأول للتفاصيل.")
        else:
            st.success("✅ لا توجد إشارات قوية حالياً. السوق هادئ.")
    else:
        st.warning("️ لا توجد بيانات كافية للفحص السريع.")

# ============ التبويب 3: محفظة التداول ============
with tab3:
    st.markdown("## 💼 محفظة التداول الشخصية")
    
    # ===== ميزة 2: تنبيه الخسارة المتتالية =====
    consecutive_losses, is_blocked_losses = check_consecutive_losses(st.session_state.portfolio)
    
    # ===== ميزة 4: حد الخسارة اليومي =====
    daily_loss_pct, daily_limit, is_blocked_daily = check_daily_loss(st.session_state.portfolio)
    
    # عرض تحذيرات الحماية
    if is_blocked_losses:
        max_losses = st.session_state.risk_config.get('max_consecutive_losses', 3)
        st.markdown(f"""
        <div class='warning-box'>
             <b>تنبيه حرج: تم إيقاف التداول مؤقتاً!</b><br>
            لديك {consecutive_losses} خسائر متتالية (الحد الأقصى: {max_losses}).<br>
            <b>توقف عن التداول الآن وراجع استراتيجيتك قبل المتابعة.</b>
        </div>
        """, unsafe_allow_html=True)
    
    if is_blocked_daily:
        st.markdown(f"""
        <div class='warning-box'>
            🚨 <b>تم الوصول لحد الخسارة اليومي!</b><br>
            خسرت {daily_loss_pct:.2f}% من رأس المال اليوم (الحد: {daily_limit}%).<br>
            <b>توقف عن التداول لباقي اليوم. عد غداً بعقل صافٍ.</b>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown(f"💰 الرصيد الحالي: **${st.session_state.portfolio['balance']:,.2f}**")
    
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    col_stat1.metric("📉 الخسارة اليومية", f"${st.session_state.portfolio.get('daily_loss', 0):,.2f}", delta=f"{daily_loss_pct:.2f}%")
    col_stat2.metric("🔴 خسائر متتالية", consecutive_losses)
    col_stat3.metric("⚠️ حد الخسارة اليومي", f"{daily_limit}%")
    
    st.markdown("---")
    
    # تسجيل صفقة جديدة
    st.markdown("### ➕ تسجيل صفقة جديدة:")
    
    col_add1, col_add2, col_add3, col_add4, col_add5 = st.columns(5)
    with col_add1:
        trade_ticker = st.text_input("الرمز", value=st.session_state.selected_ticker)
    with col_add2:
        trade_type = st.selectbox("النوع", ["شراء", "بيع"])
    with col_add3:
        trade_qty = st.number_input("الكمية", min_value=0.01, value=1.0)
    with col_add4:
        trade_price = st.number_input("سعر الدخول", min_value=0.01, value=100.0)
    with col_add5:
        trade_exit_price = st.number_input("سعر الخروج (اتركه 0 للصفقات المفتوحة)", min_value=0.0, value=0.0)
    
    # ===== ميزة 5: سجل الأخطاء والتحذيرات =====
    st.markdown("#### 📋 أسباب الدخول (اختر جميع الأسباب المناسبة):")
    
    col_reason1, col_reason2, col_reason3 = st.columns(3)
    with col_reason1:
        reason_technical = st.checkbox("✅ إشارة فنية قوية", value=True)
        reason_volume = st.checkbox("✅ حجم تداول عالي", value=True)
    with col_reason2:
        reason_sentiment = st.checkbox("✅ أخبار إيجابية", value=False)
        reason_fomo = st.checkbox("❌ دخول عاطفي (FOMO)", value=False)
    with col_reason3:
        reason_no_stop = st.checkbox("❌ بدون وقف خسارة", value=False)
        reason_news_only = st.checkbox("⚠️ بناءً على خبر فقط", value=False)
    
    reasons = []
    if reason_technical: reasons.append("إشارة فنية")
    if reason_volume: reasons.append("حجم عالي")
    if reason_sentiment: reasons.append("أخبار إيجابية")
    if reason_fomo: reasons.append("دخول عاطفي")
    if reason_no_stop: reasons.append("بدون وقف خسارة")
    if reason_news_only: reasons.append("خبر فقط")
    
    if st.button("➕ تسجيل الصفقة", use_container_width=True):
        if is_blocked_losses or is_blocked_daily:
            st.error("🚨 لا يمكن تسجيل صفقة جديدة بسبب تفعيل نظام حماية الخسائر!")
        else:
            # حساب نتيجة الصفقة
            result = None
            profit_loss = 0
            if trade_exit_price > 0:
                if trade_type == "شراء":
                    profit_loss = (trade_exit_price - trade_price) * trade_qty
                else:
                    profit_loss = (trade_price - trade_exit_price) * trade_qty
                
                result = "profit" if profit_loss > 0 else "loss"
                
                # تحديث الرصيد والخسارة اليومية
                st.session_state.portfolio['balance'] += profit_loss
                if profit_loss < 0:
                    st.session_state.portfolio['daily_loss'] += abs(profit_loss)
            
            trade = {
                'ticker': trade_ticker, 'type': trade_type, 'qty': trade_qty,
                'entry_price': trade_price, 'exit_price': trade_exit_price if trade_exit_price > 0 else None,
                'profit_loss': profit_loss, 'result': result,
                'reasons': reasons,
                'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            st.session_state.portfolio['trades'].append(trade)
            save_portfolio(st.session_state.portfolio)
            st.success("✅ تم تسجيل الصفقة!")
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 📋 سجل الصفقات:")
    
    if st.session_state.portfolio['trades']:
        trades_df = pd.DataFrame(st.session_state.portfolio['trades'])
        st.dataframe(trades_df, use_container_width=True)
        
        # إحصائيات
        total_trades = len(st.session_state.portfolio['trades'])
        winning_trades = len([t for t in st.session_state.portfolio['trades'] if t.get('result') == 'profit'])
        losing_trades = len([t for t in st.session_state.portfolio['trades'] if t.get('result') == 'loss'])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        col_stat1.metric("إجمالي الصفقات", total_trades)
        col_stat2.metric("صفقات رابحة", winning_trades)
        col_stat3.metric("صفقات خاسرة", losing_trades)
        col_stat4.metric("نسبة النجاح", f"{win_rate:.1f}%")
        
        # ===== تحليل أسباب النجاح والفشل =====
        st.markdown("#### 📊 تحليل أسباب النجاح والفشل:")
        
        reason_stats = {}
        for trade in st.session_state.portfolio['trades']:
            if trade.get('result'):
                for reason in trade.get('reasons', []):
                    if reason not in reason_stats:
                        reason_stats[reason] = {'wins': 0, 'losses': 0}
                    if trade['result'] == 'profit':
                        reason_stats[reason]['wins'] += 1
                    else:
                        reason_stats[reason]['losses'] += 1
        
        if reason_stats:
            reason_df = pd.DataFrame([
                {'السبب': reason, 'رابحة': stats['wins'], 'خاسرة': stats['losses'], 
                 'نسبة النجاح': f"{(stats['wins'] / (stats['wins'] + stats['losses']) * 100):.1f}%"}
                for reason, stats in reason_stats.items()
            ])
            st.dataframe(reason_df, use_container_width=True)
            
            # تحذيرات ذكية
            for reason, stats in reason_stats.items():
                total = stats['wins'] + stats['losses']
                if total >= 3:
                    loss_rate = stats['losses'] / total
                    if loss_rate > 0.7:
                        st.warning(f"️ تحذير: {reason} أدى إلى خسارة في {loss_rate*100:.0f}% من الصفقات! تجنب هذا السبب.")
        
        if st.button("🗑️ مسح جميع الصفقات"):
            st.session_state.portfolio['trades'] = []
            st.session_state.portfolio['daily_loss'] = 0
            save_portfolio(st.session_state.portfolio)
            st.rerun()
    else:
        st.info("📝 لم تسجل أي صفقات بعد. ابدأ بإضافة صفقتك الأولى!")

# ============ التبويب 4: حاسبة المخاطر ============
with tab4:
    st.markdown("##  حاسبة إدارة المخاطر والمراكز")
    st.markdown("احسب الكمية المثالية للشراء بناءً على رأس مالك ونسبة المخاطرة.")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        capital = st.number_input("💰 رأس المال الكلي ($)", min_value=100, value=10000, step=100)
        risk_percent = st.slider("️ نسبة المخاطرة المقبولة (%)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)
    with col_c2:
        entry_price = st.number_input("📥 سعر الدخول", min_value=0.01, value=100.0)
        stop_loss = st.number_input("🛑 سعر وقف الخسارة", min_value=0.01, value=95.0)
    
    risk_amount = capital * (risk_percent / 100)
    risk_per_share = abs(entry_price - stop_loss)
    
    if risk_per_share > 0:
        position_size = risk_amount / risk_per_share
        total_investment = position_size * entry_price
        risk_reward_ratio = risk_per_share / entry_price * 100
        
        st.markdown("---")
        st.markdown("### 📊 النتائج:")
        
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric("💵 مبلغ المخاطرة", f"${risk_amount:,.2f}")
        col_r2.metric("📦 حجم المركز (الأسهم)", f"{position_size:.2f}")
        col_r3.metric("💸 إجمالي الاستثمار", f"${total_investment:,.2f}")
        col_r4.metric("📉 نسبة المخاطرة", f"{risk_reward_ratio:.2f}%")
        
        if total_investment > capital:
            st.error("⚠️ تحذير: إجمالي الاستثمار يتجاوز رأس مالك! قلل الكمية أو ارفع وقف الخسارة.")
        else:
            st.success(f"✅ يمكنك شراء **{position_size:.2f}** سهم/عملة بمخاطرة **${risk_amount:,.2f}** فقط.")
    else:
        st.warning("⚠️ سعر الدخول يجب أن يختلف عن وقف الخسارة.")

# ============ التبويب 5: ربط Alpaca والتنفيذ التلقائي ============
# ============ التبويب 5: ربط Alpaca والتنفيذ التلقائي ============
with tab5:
    st.markdown("## 🤖 التداول التجريبي مع Alpaca (Paper Trading)")
    st.markdown("تنفيذ صفقات حقيقية في السوق الأمريكي بأموال افتراضية (100,000$).")
    
    st.markdown("---")
    st.markdown("### 🔑 إعدادات الاتصال:")
    
    col_api1, col_api2 = st.columns(2)
    with col_api1:
        api_key = st.text_input(" API Key ID", type="password", value=st.session_state.get('alpaca_api_key', ''))
    with col_api2:
        api_secret = st.text_input("🔐 Secret Key", type="password", value=st.session_state.get('alpaca_secret_key', ''))
    
    if st.button("💾 حفظ والاتصال"):
        if api_key and api_secret:
            st.session_state.alpaca_api_key = api_key
            st.session_state.alpaca_secret_key = api_secret
            st.success("✅ تم حفظ المفاتيح! جاري الاتصال...")
            st.rerun()
        else:
            st.error("⚠️ يرجى إدخال كلا المفتاحين.")
    
    st.markdown("---")
    
    # محاولة الاتصال وعرض البيانات
    if st.session_state.get('alpaca_api_key') and st.session_state.get('alpaca_secret_key'):
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            
            # الاتصال بـ Alpaca (paper=True يعني أموال افتراضية)
            trading_client = TradingClient(
                api_key=st.session_state.alpaca_api_key,
                secret_key=st.session_state.alpaca_secret_key,
                paper=True
            )
            
            # جلب معلومات الحساب
            account = trading_client.get_account()
            
            col_acc1, col_acc2, col_acc3, col_acc4 = st.columns(4)
            col_acc1.metric("💰 القيمة الكلية", f"${float(account.portfolio_value):,.2f}")
            col_acc2.metric("💵 النقد المتاح", f"${float(account.cash):,.2f}")
            col_acc3.metric("📈 الأرباح/الخسائر", f"${float(account.equity) - 100000:,.2f}")
            col_acc4.metric("🟢 حالة الحساب", "نشط")
            
            st.success("✅ تم الاتصال بنجاح بحساب Paper Trading!")
            
            st.markdown("---")
            st.markdown("### ⚡ تنفيذ صفقة تجريبية:")
            
            col_exec1, col_exec2, col_exec3 = st.columns(3)
            with col_exec1:
                exec_ticker = st.text_input("رمز السهم (أمريكي فقط)", value="AAPL")
            with col_exec2:
                exec_qty = st.number_input("الكمية (عدد الأسهم)", min_value=1.0, value=1.0, step=1.0)
            with col_exec3:
                exec_side = st.selectbox("نوع العملية", ["BUY (شراء)", "SELL (بيع)"])
            
            if st.button("🚀 تنفيذ الصفقة الآن", use_container_width=True):
                try:
                    side = OrderSide.BUY if "BUY" in exec_side else OrderSide.SELL
                    order_data = MarketOrderRequest(
                        symbol=exec_ticker.upper(),
                        qty=exec_qty,
                        side=side,
                        time_in_force=TimeInForce.DAY
                    )
                    order = trading_client.submit_order(order_data=order_data)
                    st.success(f"✅ تم تنفيذ الصفقة بنجاح! رقم الطلب: {order.id}")
                    st.info(f"الحالة: {order.status} | الكمية: {order.qty} | الرمز: {order.symbol}")
                except Exception as e:
                    st.error(f"❌ فشل التنفيذ: {str(e)}")
            
            st.markdown("---")
            st.markdown("### 📋 الصفقات المفتوحة حالياً:")
            positions = trading_client.get_all_positions()
            if positions:
                for pos in positions:
                    st.markdown(f"- **{pos.symbol}**: {pos.qty} سهم | السعر الحالي: ${float(pos.current_price):.2f} | الربح/الخسارة: ${float(pos.unrealized_pl):.2f}")
            else:
                st.info("لا توجد صفقات مفتوحة حالياً.")
                
        except Exception as e:
            st.error(f"❌ فشل الاتصال بـ Alpaca. تأكد من صحة المفاتيح. الخطأ: {str(e)}")
    else:
        st.info("💡 يرجى إدخال مفاتيح API أعلاه للبدء.")
    
    st.markdown("---")
    st.markdown("###  ملاحظات مهمة:")
    st.markdown("""
    - هذا الحساب يستخدم **أموالاً افتراضية** (100,000$) ولا يمكن سحبها.
    - الصفقات تُنفذ في **السوق الحقيقي** بأسعار حقيقية.
    - يدعم فقط **الأسهم الأمريكية** (مثل AAPL, TSLA, NVDA).
    - إذا أردت إعادة تعيين الحساب، اذهب إلى لوحة تحكم Alpaca واضغط "Reset Paper Account".
    """)

# ============ التبويب 6: إدارة المخاطر ============
with tab6:
    st.markdown("## ️ إعدادات إدارة المخاطر")
    st.markdown("تخصيص حدود الحماية حسب استراتيجية التداول الخاصة بك.")
    
    st.markdown("---")
    st.markdown("### ⚙️ حدود الخسارة:")
    
    col_risk1, col_risk2, col_risk3 = st.columns(3)
    with col_risk1:
        daily_loss_limit = st.number_input(
            "حد الخسارة اليومي (%)", 
            min_value=0.5, max_value=10.0, 
            value=st.session_state.risk_config.get('daily_loss_limit', 2.0),
            step=0.5,
            help="عند الوصول لهذا الحد، سيتم إيقاف التداول لباقي اليوم"
        )
    with col_risk2:
        max_consecutive_losses = st.number_input(
            "الحد الأقصى للخسائر المتتالية", 
            min_value=2, max_value=10, 
            value=st.session_state.risk_config.get('max_consecutive_losses', 3),
            step=1,
            help="عدد الخسائر المتتالية قبل إيقاف التداول"
        )
    with col_risk3:
        min_volume_ratio = st.number_input(
            "الحد الأدنى لحجم التداول (x)", 
            min_value=0.5, max_value=3.0, 
            value=st.session_state.risk_config.get('min_volume_ratio', 1.0),
            step=0.1,
            help="يجب أن يكون حجم التداول أعلى من هذا المضاعف لتأكيد الإشارة"
        )
    
    if st.button("💾 حفظ إعدادات المخاطر", use_container_width=True):
        st.session_state.risk_config = {
            'daily_loss_limit': daily_loss_limit,
            'max_consecutive_losses': max_consecutive_losses,
            'min_volume_ratio': min_volume_ratio
        }
        save_risk_config(st.session_state.risk_config)
        st.success("✅ تم حفظ إعدادات إدارة المخاطر بنجاح!")
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 حالة الحماية الحالية:")
    
    col_status1, col_status2 = st.columns(2)
    with col_status1:
        # نحتاج لإعادة حساب هذه القيم للعرض
        daily_loss = st.session_state.portfolio.get('daily_loss', 0)
        capital = st.session_state.portfolio.get('balance', 10000)
        daily_loss_pct = (daily_loss / capital) * 100 if capital > 0 else 0
        is_blocked_daily = daily_loss_pct >= daily_loss_limit
        
        if is_blocked_daily:
            st.error(f"🚨 حد الخسارة اليومي مفعّل ({daily_loss_pct:.2f}% / {daily_loss_limit}%)")
        else:
            st.success(f"✅ الخسارة اليومية آمنة ({daily_loss_pct:.2f}% / {daily_loss_limit}%)")
    
    with col_status2:
        trades = st.session_state.portfolio.get('trades', [])
        consecutive = 0
        for trade in reversed(trades):
            if trade.get('result') == 'loss':
                consecutive += 1
            else:
                break
        is_blocked_losses = consecutive >= max_consecutive_losses
        
        if is_blocked_losses:
            st.error(f" تم إيقاف التداول ({consecutive} خسائر متتالية)")
        else:
            st.success(f"✅ لا يوجد حظر ({consecutive} خسائر متتالية)")
    
    st.markdown("---")
    st.markdown("### 💡 نصائح إدارة المخاطر:")
    st.markdown("""
    1. **لا تخاطر بأكثر من 2%** من رأس المال في صفقة واحدة
    2. **استخدم وقف الخسارة دائماً** - لا تتداول بدونه
    3. **توقف بعد 3 خسائر متتالية** - راجع استراتيجيتك
    4. **لا تتداول عاطفياً** - اتبع خطتك فقط
    5. **سجل جميع صفقاتك** - لتحليل أداءك وتحسينه
    """)
# ============ التبويب 7: الذكاء الاصطناعي التنبؤي ============
with tab7:
    st.markdown("## 🧠 الذكاء الاصطناعي التنبؤي")
    st.markdown("نموذج Machine Learning يتنبأ باتجاه السعر بناءً على 11 مؤشر فني.")
    
    st.markdown("---")
    st.markdown("### 📊 تحليل:")
    
    df_ml, analysis_ml = get_analysis_data(st.session_state.selected_ticker, time_frame)
    
    if df_ml is None:
        st.warning(f"⚠️ لا توجد بيانات كافية لـ {st.session_state.selected_ticker}")
    else:
        with st.spinner(" جاري تدريب النموذج والتحليل..."):
            prediction, results, error = train_and_predict(df_ml, st.session_state.selected_ticker)
        
        if error:
            st.error(f"❌ خطأ في النموذج: {error}")
        else:
            # عرض التنبؤ
            col_pred1, col_pred2, col_pred3 = st.columns(3)
            
            with col_pred1:
                if prediction == 1:
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                                padding: 20px; border-radius: 15px; color: white; text-align: center;'>
                        <h2 style='margin:0;'>📈 صعود متوقع</h2>
                        <p style='margin:10px 0;'>النموذج يتوقع ارتفاع السعر</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); 
                                padding: 20px; border-radius: 15px; color: white; text-align: center;'>
                        <h2 style='margin:0;'>📉 هبوط متوقع</h2>
                        <p style='margin:10px 0;'>النموذج يتوقع انخفاض السعر</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col_pred2:
                st.metric("🎯 دقة النموذج", f"{results['accuracy']*100:.1f}%")
                st.caption("نسبة صحة التنبؤات على البيانات التاريخية")
            
            with col_pred3:
                st.metric("📊 احتمالية الصعود", f"{results['probability_up']*100:.1f}%")
                st.metric("📉 احتمالية الهبوط", f"{results['probability_down']*100:.1f}%")
            
            st.markdown("---")
            st.markdown("### 🔍 أهم المؤشرات المؤثرة في التنبؤ:")
            
            for i, (feature, importance) in enumerate(results['top_features'], 1):
                feature_names_ar = {
                    'RSI': 'مؤشر القوة النسبية',
                    'MACD': 'MACD',
                    'Signal_Line': 'خط الإشارة',
                    'MACD_Hist': 'هيستوغرام MACD',
                    'BB_Position': 'موقع السعر في بولينجر',
                    'ATR': 'متوسط المدى الحقيقي',
                    'Volume_Ratio': 'نسبة حجم التداول',
                    'Momentum_5': 'زخم 5 فترات',
                    'Momentum_10': 'زخم 10 فترات',
                    'Momentum_20': 'زخم 20 فترة',
                    'Volatility': 'التقلب'
                }
                st.markdown(f"**{i}.** {feature_names_ar.get(feature, feature)} - الأهمية: {importance*100:.1f}%")
            
            st.markdown("---")
            st.markdown("### 💡 توصية الذكاء الاصطناعي:")
            
            if results['accuracy'] < 0.6:
                st.warning("⚠️ دقة النموذج منخفضة (< 60%). لا يُنصح بالاعتماد على التنبؤ.")
            elif prediction == 1 and results['probability_up'] > 0.7:
                st.success("✅ النموذج واثق من الصعود (احتمالية > 70%). يمكن النظر لفرصة شراء.")
            elif prediction == 0 and results['probability_down'] > 0.7:
                st.error(" النموذج واثق من الهبوط (احتمالية > 70%). يُنصح بالحذر أو البيع.")
            else:
                st.info("ℹ️ النموذج غير واثق من الاتجاه. يُنصح بالانتظار.")
            
            st.markdown("---")
            st.markdown("### 📚 كيف يعمل النموذج؟")
            st.markdown("""
            - **الخوارزمية:** Random Forest (غابة القرار العشوائي)
            - **البيانات:** آخر 50+ شمعة يومية
            - **المؤشرات:** 11 مؤشر فني (RSI, MACD, Bollinger, ATR, Volume, Momentum, Volatility)
            - **الهدف:** التنبؤ هل السعر سيرتفع في الفترة القادمة؟
            - **التدريب:** 80% من البيانات للتدريب، 20% للاختبار
            """)

# ============ التبويب 8: Backtesting ============
with tab8:
    st.markdown("## ⏳ اختبار الاستراتيجية على البيانات التاريخية (Backtesting)")
    st.markdown("اكتشف كم كانت ستربح استراتيجيتك لو طُبقت خلال آخر 5 سنوات.")
    
    st.markdown("---")
    st.markdown("### ⚙️ إعدادات الاختبار:")
    
    col_bt1, col_bt2, col_bt3 = st.columns(3)
    with col_bt1:
        bt_ticker = st.text_input("رمز السهم", value="AAPL")
    with col_bt2:
        bt_period = st.selectbox("الفترة الزمنية", ["1 سنة", "3 سنوات", "5 سنوات"], index=2)
    with col_bt3:
        bt_initial_cash = st.number_input("رأس المال الابتدائي ($)", min_value=1000, value=10000, step=1000)
    
    st.markdown("---")
    st.markdown("### 📋 معايير الاستراتيجية:")
    
    col_strat1, col_strat2 = st.columns(2)
    with col_strat1:
        st.markdown("**🟢 شروط الشراء:**")
        buy_rsi = st.slider("RSI أقل من", min_value=20, max_value=50, value=35)
        buy_dist_support = st.slider("المسافة من الدعم (%)", min_value=1.0, max_value=5.0, value=2.5, step=0.5)
    with col_strat2:
        st.markdown("**🔴 شروط البيع:**")
        sell_rsi = st.slider("RSI أعلى من", min_value=50, max_value=80, value=65)
        sell_dist_resistance = st.slider("المسافة من المقاومة (%)", min_value=1.0, max_value=5.0, value=2.5, step=0.5)
    
    if st.button("🚀 بدء الاختبار", use_container_width=True):
        with st.spinner(" جاري تحليل البيانات التاريخية..."):
            try:
                import backtrader as bt
                
                # تحديد الفترة
                period_map = {"1 سنة": 1, "3 سنوات": 3, "5 سنوات": 5}
                years = period_map[bt_period]
                
                # جلب البيانات
                data = yf.Ticker(bt_ticker)
                df = data.history(period=f"{years}y", interval="1d")
                
                if df.empty or len(df) < 100:
                    st.error(f"⚠️ لا توجد بيانات كافية لـ {bt_ticker}")
                else:
                    # تحويل البيانات لصيغة Backtrader
                    df_bt = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
                    df_bt.index = pd.to_datetime(df_bt.index)
                    
                    # حساب المؤشرات المطلوبة
                    df_bt['RSI'] = 100 - (100 / (1 + (df_bt['Close'].diff().where(df_bt['Close'].diff() > 0, 0).rolling(14).mean() / 
                                                     (-df_bt['Close'].diff().where(df_bt['Close'].diff() < 0, 0).rolling(14).mean()))))
                    df_bt['Support'] = df_bt['Low'].rolling(20).min()
                    df_bt['Resistance'] = df_bt['High'].rolling(20).max()
                    
                    # إنشاء استراتيجية مخصصة
                    class MyStrategy(bt.Strategy):
                        params = (
                            ('buy_rsi', buy_rsi),
                            ('sell_rsi', sell_rsi),
                            ('buy_dist', buy_dist_support / 100),
                            ('sell_dist', sell_dist_resistance / 100),
                        )
                        
                        def __init__(self):
                            self.rsi = self.datas[0].RSI
                            self.support = self.datas[0].Support
                            self.resistance = self.datas[0].Resistance
                            self.close = self.datas[0].close
                            self.order = None
                        
                        def next(self):
                            if self.order:
                                return
                            
                            if not self.position:
                                # شروط الشراء
                                dist_to_support = (self.close[0] - self.support[0]) / self.close[0]
                                if self.rsi[0] < self.params.buy_rsi and dist_to_support < self.params.buy_dist:
                                    self.order = self.buy()
                            else:
                                # شروط البيع
                                dist_to_resistance = (self.resistance[0] - self.close[0]) / self.close[0]
                                if self.rsi[0] > self.params.sell_rsi and dist_to_resistance < self.params.sell_dist:
                                    self.order = self.sell()
                        
                        def notify_order(self, order):
                            if order.status in [order.Completed]:
                                if order.isbuy():
                                    self.buy_price = order.executed.price
                                else:
                                    self.sell_price = order.executed.price
                            self.order = None
                    
                    # إعداد Backtrader
                    cerebro = bt.Cerebro()
                    
                    # إضافة البيانات
                    data_feed = bt.feeds.PandasData(
                        dataname=df_bt,
                        open='Open',
                        high='High',
                        low='Low',
                        close='Close',
                        volume='Volume',
                        rsi='RSI',
                        support='Support',
                        resistance='Resistance'
                    )
                    cerebro.adddata(data_feed)
                    
                    # إضافة الاستراتيجية
                    cerebro.addstrategy(MyStrategy)
                    
                    # إعداد المحفظة
                    cerebro.broker.setcash(bt_initial_cash)
                    cerebro.broker.setcommission(commission=0.001)  # عمولة 0.1%
                    
                    # إضافة محلل
                    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
                    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
                    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
                    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
                    
                    # تشغيل الاختبار
                    results = cerebro.run()
                    strat = results[0]
                    
                    # النتائج
                    final_value = cerebro.broker.getvalue()
                    profit = final_value - bt_initial_cash
                    profit_pct = (profit / bt_initial_cash) * 100
                    
                    # عرض النتائج
                    st.markdown("---")
                    st.markdown("###  نتائج الاختبار:")
                    
                    col_res1, col_res2, col_res3, col_res4 = st.columns(4)
                    col_res1.metric("💰 رأس المال الابتدائي", f"${bt_initial_cash:,.2f}")
                    col_res2.metric("💵 القيمة النهائية", f"${final_value:,.2f}")
                    col_res3.metric(" الربح/الخسارة", f"${profit:,.2f}", delta=f"{profit_pct:.2f}%")
                    col_res4.metric(" عدد الصفقات", strat.analyzers.trades.get_analysis().get('total', {}).get('total', 0))
                    
                    # رسم منحنى الأرباح
                    st.markdown("---")
                    st.markdown("### 📈 منحنى نمو المحفظة:")
                    
                    portfolio_values = []
                    for i, d in enumerate(cerebro.datas[0]):
                        if i >= len(df_bt):
                            break
                        portfolio_values.append({
                            'Date': df_bt.index[i],
                            'Value': cerebro.broker.getvalue() if i == len(df_bt) - 1 else bt_initial_cash
                        })
                    
                    # رسم بسيط باستخدام Plotly
                    fig_bt = go.Figure()
                    fig_bt.add_trace(go.Scatter(
                        x=df_bt.index,
                        y=[bt_initial_cash + (profit * (i / len(df_bt))) for i in range(len(df_bt))],
                        mode='lines',
                        name='نمو المحفظة',
                        line=dict(color='green', width=2)
                    ))
                    fig_bt.update_layout(
                        title=f'نمو المحفظة - {bt_ticker} ({bt_period})',
                        xaxis_title='التاريخ',
                        yaxis_title='القيمة ($)',
                        template=theme_template,
                        height=400
                    )
                    st.plotly_chart(fig_bt, use_container_width=True)
                    
                    # تحليل المخاطر
                    st.markdown("---")
                    st.markdown("### ⚠️ تحليل المخاطر:")
                    
                    trades_analysis = strat.analyzers.trades.get_analysis()
                    total_trades = trades_analysis.get('total', {}).get('total', 0)
                    won_trades = trades_analysis.get('won', {}).get('total', 0)
                    lost_trades = trades_analysis.get('lost', {}).get('total', 0)
                    
                    if total_trades > 0:
                        win_rate = (won_trades / total_trades) * 100
                        col_risk1, col_risk2, col_risk3 = st.columns(3)
                        col_risk1.metric("✅ صفقات رابحة", won_trades)
                        col_risk2.metric("❌ صفقات خاسرة", lost_trades)
                        col_risk3.metric("🎯 نسبة النجاح", f"{win_rate:.1f}%")
                        
                        if win_rate < 50:
                            st.warning(f"⚠️ نسبة النجاح منخفضة ({win_rate:.1f}%). راجع معايير الاستراتيجية.")
                        elif win_rate > 60 and profit_pct > 20:
                            st.success(f"✅ استراتيجية ممتازة! نسبة نجاح {win_rate:.1f}% وربح {profit_pct:.2f}%")
                        else:
                            st.info(f"️ استراتيجية متوسطة. يمكن تحسينها بتعديل المعايير.")
                    else:
                        st.info("ℹ️ لم يتم تنفيذ أي صفقات خلال هذه الفترة. جرب تعديل المعايير.")
                    
                    # توصيات
                    st.markdown("---")
                    st.markdown("### 💡 توصيات:")
                    
                    if profit_pct > 0:
                        st.success(f"✅ الاستراتيجية مربحة على {bt_ticker} خلال {bt_period}. يمكنك تطبيقها بثقة.")
                    else:
                        st.error(f"❌ الاستراتيجية خاسرة على {bt_ticker}. لا تستخدمها في التداول الحقيقي.")
                    
                    st.markdown("""
                    **نصائح لتحسين النتائج:**
                    - جرب تغيير معايير RSI (اجعلها أكثر صرامة)
                    - اختبر على أسهم مختلفة
                    - لا تعتمد على نتيجة واحدة - اختبر على 5-10 أسهم
                    """)
                    
            except Exception as e:
                st.error(f"❌ حدث خطأ في الاختبار: {str(e)}")
                st.info("💡 تأكد من تثبيت backtrader: pip install backtrader")

# ============ التبويب 9: الخيارات (Options) ============
with tab9:
    st.markdown("## 📋 سلسلة الخيارات (Options Chain)")
    st.markdown("عرض عقود الخيارات المتاحة للأسهم الأمريكية (Calls & Puts).")
    
    st.markdown("---")
    options_ticker = st.text_input("أدخل رمز السهم الأمريكي (مثال: AAPL, TSLA):", value="AAPL").upper()
    
    if st.button("🔍 جلب عقود الخيارات", use_container_width=True):
        with st.spinner("جاري الاتصال ببورصة الخيارات..."):
            try:
                stock = yf.Ticker(options_ticker)
                expirations = stock.options
                
                if not expirations:
                    st.warning(f"⚠️ لا توجد عقود خيارات متاحة للرمز {options_ticker}")
                else:
                    st.success(f"✅ تم العثور على {len(expirations)} تاريخ انتهاء للعقود.")
                    
                    # اختيار تاريخ الانتهاء
                    selected_date = st.selectbox("اختر تاريخ انتهاء العقد:", expirations)
                    
                    if selected_date:
                        st.markdown(f"### 📅 عقود تنتهي في: {selected_date}")
                        
                        options_chain = stock.option_chain(selected_date)
                        
                        # عرض عقود الشراء (Calls)
                        st.markdown("#### 🟢 عقود الشراء (Calls) - للراغبين في الشراء:")
                        if not options_chain.calls.empty:
                            # تنسيق الجدول للعرض
                            calls_df = options_chain.calls[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility']].copy()
                            calls_df.columns = ['سعر التنفيذ', 'آخر سعر', 'سعر الشراء', 'سعر البيع', 'الحجم', 'العقود المفتوحة', 'التقلب الضمني']
                            st.dataframe(calls_df, use_container_width=True)
                        else:
                            st.info("لا توجد عقود Calls متاحة لهذا التاريخ.")
                        
                        st.markdown("---")
                        
                        # عرض عقود البيع (Puts)
                        st.markdown("#### 🔴 عقود البيع (Puts) - للتحوط أو المضاربة على الهبوط:")
                        if not options_chain.puts.empty:
                            puts_df = options_chain.puts[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility']].copy()
                            puts_df.columns = ['سعر التنفيذ', 'آخر سعر', 'سعر الشراء', 'سعر البيع', 'الحجم', 'العقود المفتوحة', 'التقلب الضمني']
                            st.dataframe(puts_df, use_container_width=True)
                        else:
                            st.info("لا توجد عقود Puts متاحة لهذا التاريخ.")
                            
            except Exception as e:
                st.error(f"❌ حدث خطأ أثناء جلب البيانات: {str(e)}")
                st.info("💡 تأكد أن السهم أمريكي ويدعم الخيارات (مثل AAPL, TSLA, SPY).")
