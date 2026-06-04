import yfinance as yf
import pandas as pd
import requests
import json
import os
import time
import numpy as np
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler

# ==========================================
# 1. الإعدادات
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')

STOP_LOSS_PERCENT = 3.0
TAKE_PROFIT_PERCENT = 6.0
TRADE_QTY = 1

GLOBAL_WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY",
    "2222.SR", "1120.SR", "ADCB.AD", "FAB.AD",
    "BTC-USD", "ETH-USD", "GC=F", "SI=F"
]

ALPACA_TRADABLE = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY"]
ALERTS_FILE = "last_alerts.json"
MODEL_FILE = "lstm_model.json"

# ==========================================
# 2. تحميل نموذج LSTM
# ==========================================
def load_lstm_models():
    """تحميل النماذج المدربة"""
    if not os.path.exists(MODEL_FILE):
        return {}
    try:
        with open(MODEL_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

LSTM_MODELS = load_lstm_models()

def predict_with_lstm(symbol, df):
    """
    التنبؤ باستخدام LSTM
    Returns: 1 (صعود), 0 (هبوط), أو None (لا يوجد نموذج)
    """
    if symbol not in LSTM_MODELS:
        return None
    
    try:
        model_data = LSTM_MODELS[symbol]
        features = model_data['features']
        
        # حساب المؤشرات
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        df['BB_Mid'] = df['Close'].rolling(20).mean()
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)
        df['BB_Position'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
        
        df['Volume_MA'] = df['Volume'].rolling(20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        
        df['Price_Change_1d'] = df['Close'].pct_change(1)
        df['Price_Change_5d'] = df['Close'].pct_change(5)
        df['Volatility'] = df['Close'].pct_change().rolling(10).std()
        
        df = df.dropna()
        if len(df) < 30:
            return None
        
        # أخذ آخر 30 يوم
        recent_data = df[features].tail(30).values
        
        # تطبيع
        scaler = MinMaxScaler()
        scaler.data_min_ = np.array(model_data['scaler_min'])
        scaler.data_max_ = np.array(model_data['scaler_max'])
        recent_scaled = scaler.transform(recent_data)
        
        # تسطيح
        recent_flat = recent_scaled.reshape(1, -1)
        
        # التنبؤ
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression()
        model.coef_ = np.array(model_data['coefficients'])
        model.intercept_ = np.array(model_data['intercept'])
        
        prediction = model.predict(recent_flat)[0]
        probability = model.predict_proba(recent_flat)[0]
        
        return {
            'prediction': prediction,
            'confidence': max(probability),
            'accuracy': model_data['test_accuracy']
        }
    except Exception as e:
        print(f"خطأ في LSTM لـ {symbol}: {e}")
        return None

# ==========================================
# 3. الدوال المساعدة
# ==========================================
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except:
        return False

def calculate_rsi(df, period=14):
    try:
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except:
        return None

def analyze_stock(ticker):
    try:
        df = yf.Ticker(ticker).history(period="60d", interval="1d")
        if df.empty or len(df) < 20:
            return None, None
        
        current_price = float(df['Close'].iloc[-1])
        support = float(df['Low'].rolling(20).min().iloc[-1])
        resistance = float(df['High'].rolling(20).max().iloc[-1])
        
        rsi_series = calculate_rsi(df)
        if rsi_series is None or rsi_series.empty:
            return None, None
        current_rsi = float(rsi_series.iloc[-1])
        
        dist_support = ((current_price - support) / current_price) * 100
        dist_resist = ((resistance - current_price) / current_price) * 100
        
        signal = None
        if dist_support <= 2.5 and current_rsi < 35:
            signal = "STRONG_BUY"
        elif dist_resist <= 2.5 and current_rsi > 65:
            signal = "STRONG_SELL"
        elif dist_support <= 4.0 and current_rsi < 40:
            signal = "BUY_WATCH"
        elif dist_resist <= 4.0 and current_rsi > 60:
            signal = "SELL_WATCH"
        
        if signal:
            return {
                'ticker': ticker, 'price': current_price, 'signal': signal,
                'support': support, 'resistance': resistance, 'rsi': current_rsi
            }, df
        return None, None
    except Exception as e:
        print(f"خطأ في {ticker}: {e}")
        return None, None

def execute_trade(ticker, side, entry_price):
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None, "مفاتيح Alpaca غير متاحة"
    
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=True
        )
        
        if side == "buy":
            suggested_sl = round(entry_price * (1 - STOP_LOSS_PERCENT / 100), 2)
            suggested_tp = round(entry_price * (1 + TAKE_PROFIT_PERCENT / 100), 2)
        else:
            suggested_sl = round(entry_price * (1 + STOP_LOSS_PERCENT / 100), 2)
            suggested_tp = round(entry_price * (1 - TAKE_PROFIT_PERCENT / 100), 2)
        
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=TRADE_QTY,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        order = client.submit_order(order_data=order_data)
        
        return {
            'order': order,
            'suggested_sl': suggested_sl,
            'suggested_tp': suggested_tp
        }, None
        
    except Exception as e:
        import traceback
        return None, f"{str(e)}\n\n{traceback.format_exc()}"

# ==========================================
# 4. المحرك الرئيسي
# ==========================================
def main():
    print(f"🤖 بدء الفحص (LSTM Enhanced) - {datetime.now()}")
    
    lstm_available = len(LSTM_MODELS) > 0
    print(f"🧠 نماذج LSTM المحملة: {len(LSTM_MODELS)}")
    
    send_telegram(f"🤖 <b>بدء الفحص (LSTM Enhanced)...</b>\n🧠 نماذج متاحة: {len(LSTM_MODELS)}\n⏰ {datetime.now().strftime('%H:%M')}")
    
    alpaca_ok = True
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        alpaca_ok = False
    
    last_alerts = {}
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                last_alerts = json.load(f)
        except:
            pass
    
    new_alerts = {}
    signals = 0
    trades = 0
    errors = 0
    lstm_filtered = 0  # عدد الإشارات التي فلترها LSTM
    
    for ticker in GLOBAL_WATCHLIST:
        print(f"\nفحص {ticker}...")
        try:
            result, df = analyze_stock(ticker)
            
            if result:
                signals += 1
                print(f"✅ إشارة RSI: {result['signal']}")
                
                # استشارة LSTM إذا كانت الإشارة قوية
                lstm_prediction = None
                if "STRONG" in result['signal'] and ticker in LSTM_MODELS and df is not None:
                    print(f"  🧠 استشارة LSTM لـ {ticker}...")
                    lstm_prediction = predict_with_lstm(ticker, df)
                    
                    if lstm_prediction:
                        print(f"  🧠 LSTM يتنبأ بـ: {'صعود' if lstm_prediction['prediction'] == 1 else 'هبوط'}")
                        print(f"  🧠 الثقة: {lstm_prediction['confidence']*100:.1f}%")
                
                alert_key = f"{ticker}_{result['signal']}"
                if alert_key in last_alerts:
                    try:
                        last_time = datetime.fromisoformat(last_alerts[alert_key])
                        if (datetime.now() - last_time).total_seconds() < 43200:
                            print(f"⏭️ تخطي (تنبيه حديث)")
                            continue
                    except:
                        pass
                
                is_buy = "BUY" in result['signal']
                is_strong = "STRONG" in result['signal']
                emoji = "🟢" if is_buy else "🔴"
                action = "شراء" if is_buy else "بيع"
                
                # تحديد قوة الإشارة مع LSTM
                if is_strong and lstm_prediction:
                    if lstm_prediction['prediction'] == 1 and is_buy:
                        strength = "قوية جداً (LSTM يؤكد) 🧠"
                        should_execute = True
                    elif lstm_prediction['prediction'] == 0 and not is_buy:
                        strength = "قوية جداً (LSTM يؤكد) 🧠"
                        should_execute = True
                    else:
                        strength = "قوية (LSTM يعارض) ️"
                        should_execute = False
                        lstm_filtered += 1
                elif is_strong:
                    strength = "قوية جداً"
                    should_execute = True
                else:
                    strength = "متوسطة"
                    should_execute = False
                
                msg = f"""
{emoji} <b>إشارة {action} {strength}!</b>

📌 <b>{result['ticker']}</b>
💰 السعر: ${result['price']:.2f}
📊 RSI: {result['rsi']:.1f}
🛡️ الدعم: ${result['support']:.2f}
🚧 المقاومة: ${result['resistance']:.2f}
"""
                
                if lstm_prediction:
                    lstm_dir = " صعود" if lstm_prediction['prediction'] == 1 else "📉 هبوط"
                    msg += f"\n🧠 <b>LSTM:</b> {lstm_dir} (ثقة: {lstm_prediction['confidence']*100:.1f}%)\n"
                
                send_telegram(msg)
                
                # التنفيذ
                if should_execute and is_strong and ticker in ALPACA_TRADABLE and alpaca_ok:
                    send_telegram(f"🤖 <b>جاري تنفيذ صفقة لـ {ticker}...</b>")
                    
                    trade_result, error = execute_trade(
                        ticker, "buy" if is_buy else "sell", result['price']
                    )
                    
                    if error:
                        errors += 1
                        send_telegram(f"❌ فشل {ticker}:\n{error[:200]}")
                    else:
                        trades += 1
                        order = trade_result['order']
                        
                        success = f"""
✅ <b>تم التنفيذ بنجاح!</b>

📌 الرمز: {ticker}
💰 سعر الدخول: ${result['price']:.2f}
📦 الكمية: {TRADE_QTY}
🔖 رقم الطلب: {order.id}

🧠 <b>تأكيد LSTM:</b> {'✅ متفق' if lstm_prediction else '⚠️ غير متاح'}

⚙️ <b>إدارة المخاطر:</b>
🛑 وقف الخسارة: ${trade_result['suggested_sl']:.2f}
🎯 جني الأرباح: ${trade_result['suggested_tp']:.2f}
"""
                        send_telegram(success)
                
                new_alerts[alert_key] = datetime.now().isoformat()
        except Exception as e:
            errors += 1
            print(f"❌ خطأ في {ticker}: {e}")
    
    summary = f"""
📊 <b>ملخص الفحص:</b>

✅ إشارات RSI: {signals}
🤖 صفقات منفذة: {trades}
🧠 إشارات فلترها LSTM: {lstm_filtered}
❌ أخطاء: {errors}
🧠 نماذج LSTM: {len(LSTM_MODELS)}

 {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    send_telegram(summary)
    
    if new_alerts:
        try:
            with open(ALERTS_FILE, 'w') as f:
                json.dump(new_alerts, f)
        except:
            pass
    
    print(f"\n✅ انتهى - إشارات: {signals}, صفقات: {trades}, فلتر LSTM: {lstm_filtered}")

if __name__ == "__main__":
    main()
