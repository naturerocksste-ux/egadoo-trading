import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime

# ==========================================
# 1. الإعدادات والمفاتيح (من GitHub Secrets)
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')

# ==========================================
# 2. قوائم المراقبة والتنفيذ
# ==========================================
# قائمة المراقبة الشاملة (لإرسال التنبيهات)
GLOBAL_WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY",  # أمريكي
    "2222.SR", "1120.SR",                            # سعودي
    "ADCB.AD", "FAB.AD",                            # إماراتي
    "BTC-USD", "ETH-USD",                           # عملات رقمية
    "GC=F", "SI=F"                                  # معادن
]

# الأصول القابلة للتنفيذ التلقائي في Alpaca (أمريكي + كريبتو فقط)
ALPACA_TRADABLE = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY", "BTC-USD", "ETH-USD"]

ALERTS_FILE = "last_alerts.json"

# ==========================================
# 3. الدوال المساعدة
# ==========================================
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        return True
    except: return False

def calculate_rsi(df, period=14):
    try:
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except: return None

def analyze_stock(ticker):
    try:
        df = yf.Ticker(ticker).history(period="60d", interval="1d")
        if df.empty or len(df) < 20: return None
        
        current_price = float(df['Close'].iloc[-1])
        support = float(df['Low'].rolling(window=20).min().iloc[-1])
        resistance = float(df['High'].rolling(window=20).max().iloc[-1])
        
        rsi_series = calculate_rsi(df)
        if rsi_series is None or rsi_series.empty: return None
        current_rsi = float(rsi_series.iloc[-1])
        
        dist_to_support = ((current_price - support) / current_price) * 100
        dist_to_resistance = ((resistance - current_price) / current_price) * 100
        
        signal = None
        # شروط قوية جداً للتنفيذ التلقائي
        if dist_to_support <= 2.5 and current_rsi < 35:
            signal = "STRONG_BUY"
        elif dist_to_resistance <= 2.5 and current_rsi > 65:
            signal = "STRONG_SELL"
        # شروط متوسطة للتنبيه فقط
        elif dist_to_support <= 4.0 and current_rsi < 40:
            signal = "BUY_WATCH"
        elif dist_to_resistance <= 4.0 and current_rsi > 60:
            signal = "SELL_WATCH"
            
        if signal:
            return {
                'ticker': ticker, 'price': current_price, 'signal': signal,
                'support': support, 'resistance': resistance, 'rsi': current_rsi
            }
        return None
    except Exception as e:
        print(f"خطأ في تحليل {ticker}: {e}")
        return None

def execute_alpaca_trade(ticker, side):
    """تنفيذ الصفقة في Alpaca (Paper Trading فقط)"""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None, "مفاتيح Alpaca غير متاحة"
    
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        # paper=True تعني أموال افتراضية 100%
        client = TradingClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY, paper=True)
        
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=1,  # سهم واحد أو عملة واحدة للأمان
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        order = client.submit_order(order_data=order_data)
        return order, None
    except Exception as e:
        return None, str(e)

# ==========================================
# 4. المحرك الرئيسي
# ==========================================
def main():
    print(f" بدء الفحص الشامل - {datetime.now()}")
    send_telegram_message(f"🤖 <b>بدء الفحص الشامل للأسواق...</b>\n⏰ {datetime.now().strftime('%H:%M')}")
    
    last_alerts = {}
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f: last_alerts = json.load(f)
        except: pass
    
    new_alerts = {}
    signals_count = 0
    trades_count = 0
    
    for ticker in GLOBAL_WATCHLIST:
        print(f"فحص {ticker}...")
        result = analyze_stock(ticker)
        
        if result:
            signals_count += 1
            alert_key = f"{ticker}_{result['signal']}"
            
            # منع تكرار التنبيه لنفس الإشارة خلال 12 ساعة
            if alert_key in last_alerts:
                try:
                    last_time = datetime.fromisoformat(last_alerts[alert_key])
                    if (datetime.now() - last_time).total_seconds() < 43200: # 12 ساعة
                        continue
                except: pass
            
            # تحديد نوع الرسالة
            is_buy = "BUY" in result['signal']
            is_strong = "STRONG" in result['signal']
            emoji = "🟢" if is_buy else "🔴"
            action_text = "شراء" if is_buy else "بيع"
            strength_text = "قوية جداً (تنفيذ تلقائي)" if is_strong else "متوسطة (مراقبة)"
            
            message = f"""
{emoji} <b>إشارة {action_text} {strength_text}!</b>

📌 <b>{result['ticker']}</b>
💰 السعر: ${result['price']:.2f}
📊 RSI: {result['rsi']:.1f}
🛡️ الدعم: ${result['support']:.2f}
🚧 المقاومة: ${result['resistance']:.2f}
"""
            send_telegram_message(message)
            
            # التنفيذ التلقائي إذا كانت الإشارة قوية والسهم مدعوم في Alpaca
            if is_strong and ticker in ALPACA_TRADABLE:
                send_telegram_message(f"🤖 <b>جاري تنفيذ صفقة تلقائية لـ {ticker}...</b>")
                order, error = execute_alpaca_trade(ticker, "buy" if is_buy else "sell")
                
                if error:
                    send_telegram_message(f"❌ فشل التنفيذ: {error}")
                else:
                    trades_count += 1
                    send_telegram_message(f"✅ <b>تم التنفيذ بنجاح!</b>\nالرمز: {ticker}\nالنوع: {'شراء' if is_buy else 'بيع'}\nالكمية: 1")
            
            new_alerts[alert_key] = datetime.now().isoformat()
    
    # الملخص النهائي
    summary = f"""
📊 <b>ملخص الفحص:</b>
✅ إشارات: {signals_count}
🤖 صفقات منفذة: {trades_count}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    send_telegram_message(summary)
    
    if new_alerts:
        with open(ALERTS_FILE, 'w') as f: json.dump(new_alerts, f)
    
    print(f"✅ انتهى الفحص")

if __name__ == "__main__":
    main()
