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

WATCHLIST = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY"]
ALERTS_FILE = "last_alerts.json"

def send_telegram_message(message):
    """إرسال رسالة مع حماية كاملة من الأخطاء"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ مفاتيح تيليجرام غير متاحة")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"خطأ تيليجرام: {e}")
        return False

def calculate_rsi(df, period=14):
    try:
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except:
        return None

def analyze_stock(ticker):
    """تحليل السهم مع حماية من الأخطاء"""
    try:
        df = yf.Ticker(ticker).history(period="60d", interval="1d")
        if df.empty or len(df) < 20:
            return None
        
        current_price = float(df['Close'].iloc[-1])
        support = float(df['Low'].rolling(window=20).min().iloc[-1])
        resistance = float(df['High'].rolling(window=20).max().iloc[-1])
        
        rsi_series = calculate_rsi(df)
        if rsi_series is None or rsi_series.empty:
            return None
        
        current_rsi = float(rsi_series.iloc[-1])
        
        dist_to_support = ((current_price - support) / current_price) * 100
        dist_to_resistance = ((resistance - current_price) / current_price) * 100
        
        signal = None
        signal_strength = None
        
        # شروط متوسطة (أكثر مرونة)
        if dist_to_support <= 3.0 and current_rsi < 40:
            signal = "buy"
            signal_strength = "شراء"
        elif dist_to_resistance <= 3.0 and current_rsi > 60:
            signal = "sell"
            signal_strength = "بيع"
            
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
    
    # إرسال رسالة بدء
    send_telegram_message(f" <b>بدء فحص الأسواق...</b>\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    last_alerts = {}
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                last_alerts = json.load(f)
        except:
            pass
    
    new_alerts = {}
    signals_found = 0
    
    for ticker in WATCHLIST:
        print(f"فحص {ticker}...")
        try:
            result = analyze_stock(ticker)
            
            if result:
                signals_found += 1
                print(f"✅ إشارة في {ticker}")
                
                alert_key = f"{ticker}_{result['signal']}"
                if alert_key in last_alerts:
                    try:
                        last_time = datetime.fromisoformat(last_alerts[alert_key])
                        hours_since = (datetime.now() - last_time).total_seconds() / 3600
                        if hours_since < 6:
                            print(f"⏭️ تخطي {ticker} (تنبيه حديث)")
                            continue
                    except:
                        pass
                
                # إرسال التنبيه
                is_buy = result['signal'] == "buy"
                emoji = "" if is_buy else "🔴"
                
                message = f"""
{emoji} <b>إشارة {result['signal_strength']}!</b>

📌 <b>{result['ticker']}</b>
💰 السعر: ${result['price']:.2f}
📊 RSI: {result['rsi']:.1f}
🛡️ الدعم: ${result['support']:.2f} ({result['dist_to_support']:.1f}%)
🚧 المقاومة: ${result['resistance']:.2f} ({result['dist_to_resistance']:.1f}%)

 {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
                send_telegram_message(message)
                new_alerts[alert_key] = datetime.now().isoformat()
        except Exception as e:
            print(f"خطأ في معالجة {ticker}: {e}")
    
    # إرسال ملخص
    summary = f"""
📊 <b>ملخص الفحص:</b>

✅ عدد الإشارات المكتشفة: {signals_found}
📋 الأسهم المفحوصة: {len(WATCHLIST)}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    send_telegram_message(summary)
    
    if new_alerts:
        try:
            with open(ALERTS_FILE, 'w') as f:
                json.dump(new_alerts, f)
        except:
            pass
    
    print(f"✅ انتهى الفحص - إشارات: {signals_found}")

if __name__ == "__main__":
    main()
