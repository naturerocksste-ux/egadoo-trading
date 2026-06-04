import yfinance as yf
import pandas as pd
import requests
import json
import os
import traceback
from datetime import datetime

# ==========================================
# 1. الإعدادات والمفاتيح
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')

# ==========================================
# 2. إعدادات إدارة المخاطر
# ==========================================
STOP_LOSS_PERCENT = 3.0
TAKE_PROFIT_PERCENT = 6.0
TRADE_QTY = 1

# ==========================================
# 3. قوائم المراقبة
# ==========================================
GLOBAL_WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY",
    "2222.SR", "1120.SR",
    "ADCB.AD", "FAB.AD",
    "BTC-USD", "ETH-USD",
    "GC=F", "SI=F"
]

ALPACA_TRADABLE = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY", "BTC-USD", "ETH-USD"]

ALERTS_FILE = "last_alerts.json"

# ==========================================
# 4. دوال مساعدة
# ==========================================
def send_telegram_message(message):
    """إرسال رسالة تيليجرام مع حماية كاملة"""
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
        if dist_to_support <= 2.5 and current_rsi < 35:
            signal = "STRONG_BUY"
        elif dist_to_resistance <= 2.5 and current_rsi > 65:
            signal = "STRONG_SELL"
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

def test_alpaca_connection():
    """اختبار الاتصال بـ Alpaca"""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return False, "مفاتيح Alpaca غير متاحة"
    
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=True
        )
        account = client.get_account()
        return True, f"متصل! الرصيد: ${float(account.cash):,.2f}"
    except Exception as e:
        return False, f"فشل الاتصال: {str(e)}"

def execute_bracket_order(ticker, side, entry_price):
    """
    تنفيذ Bracket Order بالطريقة الصحيحة
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None, "مفاتيح Alpaca غير متاحة"
    
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest
        from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
        
        client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=True
        )
        
        # حساب الأسعار
        if side == "buy":
            stop_loss_price = round(entry_price * (1 - STOP_LOSS_PERCENT / 100), 2)
            take_profit_price = round(entry_price * (1 + TAKE_PROFIT_PERCENT / 100), 2)
        else:
            stop_loss_price = round(entry_price * (1 + STOP_LOSS_PERCENT / 100), 2)
            take_profit_price = round(entry_price * (1 - TAKE_PROFIT_PERCENT / 100), 2)
        
        print(f"جاري تنفيذ {side} لـ {ticker} بسعر {entry_price}")
        print(f"وقف الخسارة: {stop_loss_price}, جني الأرباح: {take_profit_price}")
        
        # ✅ الطريقة الصحيحة: بناء Bracket Order في خطوة واحدة
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=TRADE_QTY,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,  # مهم جداً!
            stop_loss=StopLossRequest(stop_price=stop_loss_price),
            take_profit=TakeProfitRequest(limit_price=take_profit_price)
        )
        
        # تنفيذ الأمر
        order = client.submit_order(order_data=order_data)
        
        return {
            'order': order,
            'stop_loss': stop_loss_price,
            'take_profit': take_profit_price,
            'has_bracket': True
        }, None
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return None, f"{str(e)}\n\n{error_detail}"
# ==========================================
# 5. المحرك الرئيسي
# ==========================================
def main():
    print(f"🤖 بدء الفحص - {datetime.now()}")
    
    # إرسال رسالة بدء
    send_telegram_message(f"🤖 <b>بدء الفحص الشامل...</b>\n {datetime.now().strftime('%H:%M')}")
    
    # اختبار الاتصال بـ Alpaca
    alpaca_ok, alpaca_msg = test_alpaca_connection()
    print(f"حالة Alpaca: {alpaca_msg}")
    if not alpaca_ok:
        send_telegram_message(f"⚠️ <b>مشكلة في Alpaca:</b>\n{alpaca_msg}")
    
    # تحميل التنبيهات السابقة
    last_alerts = {}
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                last_alerts = json.load(f)
        except:
            pass
    
    new_alerts = {}
    signals_count = 0
    trades_count = 0
    errors_count = 0
    
    for ticker in GLOBAL_WATCHLIST:
        print(f"\nفحص {ticker}...")
        try:
            result = analyze_stock(ticker)
            
            if result:
                signals_count += 1
                print(f"✅ إشارة في {ticker}: {result['signal']}")
                
                alert_key = f"{ticker}_{result['signal']}"
                
                # التحقق من التكرار
                if alert_key in last_alerts:
                    try:
                        last_time = datetime.fromisoformat(last_alerts[alert_key])
                        if (datetime.now() - last_time).total_seconds() < 43200:
                            print(f"️ تخطي {ticker} (تنبيه حديث)")
                            continue
                    except:
                        pass
                
                # إرسال التنبيه
                is_buy = "BUY" in result['signal']
                is_strong = "STRONG" in result['signal']
                emoji = "🟢" if is_buy else "🔴"
                action_text = "شراء" if is_buy else "بيع"
                strength_text = "قوية جداً" if is_strong else "متوسطة"
                
                message = f"""
{emoji} <b>إشارة {action_text} {strength_text}!</b>

📌 <b>{result['ticker']}</b>
💰 السعر: ${result['price']:.2f}
 RSI: {result['rsi']:.1f}
🛡️ الدعم: ${result['support']:.2f}
🚧 المقاومة: ${result['resistance']:.2f}
"""
                send_telegram_message(message)
                
                # التنفيذ التلقائي
                if is_strong and ticker in ALPACA_TRADABLE and alpaca_ok:
                    send_telegram_message(f" <b>جاري تنفيذ صفقة لـ {ticker}...</b>")
                    
                    result_trade, error = execute_bracket_order(
                        ticker,
                        "buy" if is_buy else "sell",
                        result['price']
                    )
                    
                    if error:
                        errors_count += 1
                        send_telegram_message(f"❌ فشل تنفيذ {ticker}:\n{error[:200]}")
                    else:
                        trades_count += 1
                        order = result_trade['order']
                        stop_loss = result_trade['stop_loss']
                        take_profit = result_trade['take_profit']
                        has_bracket = result_trade['has_bracket']
                        
                        bracket_text = "✅ مع وقف خسارة وجني أرباح" if has_bracket else "⚠️ أمر عادي (Bracket غير مدعوم)"
                        
                        success_msg = f"""
✅ <b>تم التنفيذ بنجاح!</b>

📌 الرمز: {ticker}
💰 سعر الدخول: ${result['price']:.2f}
🛑 وقف الخسارة: ${stop_loss:.2f} (-{STOP_LOSS_PERCENT}%)
🎯 جني الأرباح: ${take_profit:.2f} (+{TAKE_PROFIT_PERCENT}%)
📦 الكمية: {TRADE_QTY}
{bracket_text}
🔖 رقم الطلب: {order.id}
"""
                        send_telegram_message(success_msg)
                
                new_alerts[alert_key] = datetime.now().isoformat()
        except Exception as e:
            errors_count += 1
            print(f"❌ خطأ في معالجة {ticker}: {e}")
            send_telegram_message(f"❌ خطأ في {ticker}:\n{str(e)[:150]}")
    
    # الملخص النهائي
    summary = f"""
📊 <b>ملخص الفحص:</b>

✅ إشارات: {signals_count}
🤖 صفقات منفذة: {trades_count}
❌ أخطاء: {errors_count}
🔌 Alpaca: {'متصل' if alpaca_ok else 'غير متصل'}
⚙️ SL={STOP_LOSS_PERCENT}%, TP={TAKE_PROFIT_PERCENT}%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    send_telegram_message(summary)
    
    # حفظ التنبيهات
    if new_alerts:
        try:
            with open(ALERTS_FILE, 'w') as f:
                json.dump(new_alerts, f)
        except Exception as e:
            print(f"خطأ في حفظ التنبيهات: {e}")
    
    print(f"\n✅ انتهى الفحص - إشارات: {signals_count}, صفقات: {trades_count}, أخطاء: {errors_count}")

if __name__ == "__main__":
    main()
