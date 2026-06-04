import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime

# ==========================================
# إعدادات تيليجرام و Alpaca (من GitHub Secrets)
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')

# ==========================================
# قائمة الأسهم للمراقبة
# ==========================================
WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY",
    "BTC-USD", "ETH-USD", "GC=F", "SI=F", "^GSPC"
]

ALERTS_FILE = "last_alerts.json"

def load_last_alerts():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, 'r') as f: return json.load(f)
    return {}

def save_last_alerts(data):
    with open(ALERTS_FILE, 'w') as f: json.dump(data, f)

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except: return False

def execute_alpaca_trade(ticker, side, qty):
    """دالة تنفيذ الصفقة في Alpaca"""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None, "مفاتيح Alpaca غير متاحة"
    
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        # paper=True تعني أموال افتراضية
        client = TradingClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY, paper=True)
        
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        order = client.submit_order(order_data=order_data)
        return order, None
    except Exception as e:
        return None, str(e)

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker):
    try:
        df = yf.Ticker(ticker).history(period="60d", interval="1d")
        if df.empty or len(df) < 20: return None
        
        current_price = float(df['Close'].iloc[-1])
        support = float(df['Low'].rolling(window=20).min().iloc[-1])
        resistance = float(df['High'].rolling(window=20).max().iloc[-1])
        
        df['RSI'] = calculate_rsi(df)
        current_rsi = float(df['RSI'].iloc[-1])
        
        dist_to_support = ((current_price - support) / current_price) * 100
        dist_to_resistance = ((resistance - current_price) / current_price) * 100
        
        signal = None
        # ننفذ الصفقة فقط على الإشارات القوية جداً لتجنب الضوضاء
        if dist_to_support <= 2.0 and current_rsi < 30:
            signal = "buy_strong"
        elif dist_to_resistance <= 2.0 and current_rsi > 70:
            signal = "sell_strong"
            
        if signal:
            return {'ticker': ticker, 'price': current_price, 'signal': signal, 'support': support, 'resistance': resistance, 'rsi': current_rsi}
        return None
    except: return None

def main():
    print(f"🤖 بدء الفحص - {datetime.now()}")
    if not TELEGRAM_BOT_TOKEN:
        print("❌ مفاتيح تيليجرام غير متاحة")
        return
    
    last_alerts = load_last_alerts()
    new_alerts = {}
    
    for ticker in WATCHLIST:
        print(f" فحص {ticker}...")
        result = analyze_stock(ticker)
        
        if result:
            alert_key = f"{ticker}_{result['signal']}"
            if alert_key in last_alerts:
                last_time = datetime.fromisoformat(last_alerts[alert_key])
                hours_since = (datetime.now() - last_time).total_seconds() / 3600
                if hours_since < 6: continue # تنبيه كل 6 ساعات لنفس السهم
            
            # تحديد نوع الرسالة والتنفيذ
            is_buy = result['signal'] == "buy_strong"
            action_text = "شراء قوية 🔥" if is_buy else "بيع قوية ⚠️"
            trade_side = "buy" if is_buy else "sell"
            
            message = f"""
🚨 <b>إشارة {action_text} + تنفيذ تلقائي!</b>

📌 <b>{result['ticker']}</b>
💰 السعر: ${result['price']:.2f}
📊 RSI: {result['rsi']:.1f}

🤖 <b>جاري تنفيذ الصفقة في Alpaca...</b>
"""
            
            # إرسال التنبيه أولاً
            send_telegram_message(message)
            
            # تنفيذ الصفقة (كمية صغيرة للتجربة: سهم واحد)
            order, error = execute_alpaca_trade(result['ticker'], trade_side, 1)
            
            if error:
                send_telegram_message(f"❌ فشل تنفيذ {result['ticker']}: {error}")
            else:
                send_telegram_message(f"✅ <b>تم تنفيذ صفقة {result['ticker']} بنجاح!</b>\nرقم الطلب: {order.id}\nالكمية: {order.qty}")
            
            new_alerts[alert_key] = datetime.now().isoformat()
    
    if new_alerts:
        save_last_alerts(new_alerts)
    print("✅ انتهى الفحص")

if __name__ == "__main__":
    main()
