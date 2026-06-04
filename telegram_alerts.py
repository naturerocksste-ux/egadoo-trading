import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime

# ==========================================
# إعدادات تيليجرام (سنملؤها من GitHub Secrets)
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# ==========================================
# قائمة الأسهم للمراقبة
# ==========================================
WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY",
    "2222.SR", "1120.SR",
    "COMI.CA",
    "ADCB.AD", "FAB.AD",
    "BTC-USD", "ETH-USD",
    "GC=F", "SI=F", "^GSPC"
]

# ==========================================
# ملف لتتبع آخر التنبيهات (لتجنب التكرار)
# ==========================================
ALERTS_FILE = "last_alerts.json"

def load_last_alerts():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_last_alerts(data):
    with open(ALERTS_FILE, 'w') as f:
        json.dump(data, f)

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ مفاتيح تيليجرام غير متاحة")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطأ في إرسال الرسالة: {e}")
        return False

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker):
    try:
        df = yf.Ticker(ticker).history(period="60d", interval="1d")
        
        if df.empty or len(df) < 20:
            return None
        
        current_price = float(df['Close'].iloc[-1])
        support = float(df['Low'].rolling(window=20).min().iloc[-1])
        resistance = float(df['High'].rolling(window=20).max().iloc[-1])
        
        df['RSI'] = calculate_rsi(df)
        current_rsi = float(df['RSI'].iloc[-1])
        
        dist_to_support = ((current_price - support) / current_price) * 100
        dist_to_resistance = ((resistance - current_price) / current_price) * 100
        
        signal = None
        
        if dist_to_support <= 2.5 and current_rsi < 35:
            signal = "🟢 شراء قوية"
        elif dist_to_support <= 3.5 and current_rsi < 40:
            signal = "🟩 شراء مبدئية"
        elif dist_to_resistance <= 2.5 and current_rsi > 65:
            signal = "🔴 بيع قوية"
        elif dist_to_resistance <= 3.5 and current_rsi > 60:
            signal = "🟥 بيع مبدئية"
        
        if signal:
            return {
                'ticker': ticker,
                'price': current_price,
                'signal': signal,
                'support': support,
                'resistance': resistance,
                'rsi': current_rsi
            }
        
        return None
        
    except Exception as e:
        print(f"️ خطأ في تحليل {ticker}: {e}")
        return None

def main():
    print(f"🤖 بدء فحص الأسواق - {datetime.now()}")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ مفاتيح تيليجرام غير متاحة. تأكد من إعداد GitHub Secrets.")
        return
    
    last_alerts = load_last_alerts()
    new_alerts = {}
    alerts_sent = 0
    
    for ticker in WATCHLIST:
        print(f" فحص {ticker}...")
        result = analyze_stock(ticker)
        
        if result:
            # مفتاح فريد لكل تنبيه (السهم + نوع الإشارة)
            alert_key = f"{ticker}_{result['signal']}"
            
            # تحقق إذا كان التنبيه قد أُرسل في آخر 4 ساعات (لتجنب التكرار)
            if alert_key in last_alerts:
                last_time = datetime.fromisoformat(last_alerts[alert_key])
                hours_since = (datetime.now() - last_time).total_seconds() / 3600
                
                if hours_since < 4:
                    print(f"⏭️ تم إرسال تنبيه {ticker} مؤخراً، تخطي...")
                    continue
            
            # إنشاء رسالة التنبيه
            message = f"""
 <b>تنبيه تداول جديد!</b>

📌 <b>{result['ticker']}</b>
💰 السعر الحالي: ${result['price']:.2f}
{result['signal']}

📊 التفاصيل:
• الدعم: ${result['support']:.2f}
• المقاومة: ${result['resistance']:.2f}
• RSI: {result['rsi']:.1f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            
            # إرسال التنبيه
            if send_telegram_message(message):
                print(f"✅ تم إرسال تنبيه {ticker}")
                new_alerts[alert_key] = datetime.now().isoformat()
                alerts_sent += 1
            else:
                print(f"❌ فشل إرسال تنبيه {ticker}")
    
    # حفظ التنبيهات الجديدة
    if new_alerts:
        save_last_alerts(new_alerts)
    
    print(f"\n📊 ملخص: تم إرسال {alerts_sent} تنبيه")
    
    # إرسال ملخص إذا لم تكن هناك تنبيهات (كل 24 ساعة)
    if alerts_sent == 0:
        summary_msg = f"""
✅ <b>تقرير دوري - لا توجد إشارات قوية</b>

تم فحص {len(WATCHLIST)} سهم/أصل.
لا توجد إشارات شراء أو بيع قوية حالياً.

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        send_telegram_message(summary_msg)

if __name__ == "__main__":
    main()