import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime

# ==========================================
# إعدادات تيليجرام و Alpaca
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')

WATCHLIST = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY", "BTC-USD", "ETH-USD"]
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
    except Exception as e:
        print(f"خطأ تيليجرام: {e}")
        return False

def test_alpaca_connection():
    """اختبار الاتصال بـ Alpaca"""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return False, "مفاتيح Alpaca غير متاحة في GitHub Secrets"
    
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY, paper=True)
        account = client.get_account()
        return True, f"الاتصال ناجح! الرصيد: ${float(account.cash):,.2f}"
    except Exception as e:
        return False, f"فشل الاتصال: {str(e)}"

def execute_alpaca_trade(ticker, side, qty):
    """تنفيذ الصفقة في Alpaca"""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
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
        signal_strength = None
        
        # شروط صارمة جداً (قوية)
        if dist_to_support <= 2.0 and current_rsi < 30:
            signal = "buy_strong"
            signal_strength = "قوية جداً"
        elif dist_to_resistance <= 2.0 and current_rsi > 70:
            signal = "sell_strong"
            signal_strength = "قوية جداً"
        # شروط متوسطة (للتجربة فقط - سننفذها)
        elif dist_to_support <= 3.0 and current_rsi < 35:
            signal = "buy_medium"
            signal_strength = "متوسطة"
        elif dist_to_resistance <= 3.0 and current_rsi > 65:
            signal = "sell_medium"
            signal_strength = "متوسطة"
            
        if signal:
            return {
                'ticker': ticker, 
                'price': current_price, 
                'signal': signal,
                'signal_strength': signal_strength,
                'support': support, 
                'resistance': resistance, 
                'rsi': current_rsi,
                'dist_to_support': dist_to_support,
                'dist_to_resistance': dist_to_resistance
            }
        return None
    except Exception as e:
        print(f"خطأ في تحليل {ticker}: {e}")
        return None

def main():
    print(f"🤖 بدء الفحص - {datetime.now()}")
    
    # اختبار الاتصال بـ Alpaca أولاً
    alpaca_ok, alpaca_msg = test_alpaca_connection()
    print(f"حالة Alpaca: {alpaca_msg}")
    
    if not alpaca_ok:
        send_telegram_message(f"❌ <b>مشكلة في Alpaca:</b>\n{alpaca_msg}\n\nلن يتم تنفيذ صفقات حتى يتم الإصلاح.")
    
    last_alerts = load_last_alerts()
    new_alerts = {}
    signals_found = 0
    trades_executed = 0
    
    for ticker in WATCHLIST:
        print(f"فحص {ticker}...")
        result = analyze_stock(ticker)
        
        if result:
            signals_found += 1
            print(f"✅ إشارة في {ticker}: {result['signal_strength']}")
            
            alert_key = f"{ticker}_{result['signal']}"
            if alert_key in last_alerts:
                last_time = datetime.fromisoformat(last_alerts[alert_key])
                hours
