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

# الأسهم الأمريكية فقط (المدعومة في Alpaca Paper Trading)
ALPACA_TRADABLE = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY"]

ALERTS_FILE = "last_alerts.json"

# ==========================================
# 4. دوال مساعدة
# ==========================================
def send_telegram_message(message):
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
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return False, "مفاتيح Alpaca غير متاحة"
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY, paper=True)
        account = client.get_account()
        return True, f"متصل! الرصيد: ${float(account.cash):,.2f}"
    except Exception as e:
        return False, f"فشل الاتصال: {str(e)}"

def cancel_all_open_orders(client, ticker=None):
    """إلغاء جميع الأوامر المعلقة (للسهم المحدد أو جميع الأسهم)"""
    try:
        if ticker:
            open_orders = client.get_orders(status='open', symbols=[ticker])
        else:
            open_orders = client.get_orders(status='open')
        
        cancelled_count = 0
        for order in open_orders:
            try:
                client.cancel_order(order.id)
                cancelled_count += 1
                print(f"  تم إلغاء أمر: {order.id} ({order.symbol})")
            except Exception as e:
                print(f"  فشل إلغاء أمر {order.id}: {e}")
        
        if cancelled_count > 0:
            print(f"✅ تم إلغاء {cancelled_count} أمر معلق")
            # انتظار قصير للتأكد من معالجة الإلغاء
            import time
            time.sleep(2)
        
        return cancelled_count
    except Exception as e:
        print(f"⚠️ خطأ في إلغاء الأوامر: {e}")
        return 0

def execute_simple_trade(ticker, side, entry_price):
    """
    تنفيذ أمر دخول بسيط فقط (بدون أوامر معلقة)
    إدارة المخاطر تتم يدوياً من Alpaca Dashboard
    """
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
        
        # إلغاء جميع الأوامر المعلقة أولاً
        print("🧹 جاري إلغاء الأوامر المعلقة...")
        try:
            open_orders = client.get_orders(status='open')
            for order in open_orders:
                client.cancel_order(order.id)
                print(f"  تم إلغاء: {order.id}")
            import time
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ خطأ في الإلغاء: {e}")
        
        # حساب أسعار مرجعية للرسالة فقط
        if side == "buy":
            suggested_sl = round(entry_price * (1 - STOP_LOSS_PERCENT / 100), 2)
            suggested_tp = round(entry_price * (1 + TAKE_PROFIT_PERCENT / 100), 2)
        else:
            suggested_sl = round(entry_price * (1 + STOP_LOSS_PERCENT / 100), 2)
            suggested_tp = round(entry_price * (1 - TAKE_PROFIT_PERCENT / 100), 2)
        
        print(f"جاري تنفيذ {side} لـ {ticker} بسعر {entry_price}")
        
        # تنفيذ أمر دخول واحد فقط
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=TRADE_QTY,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        order = client.submit_order(order_data=order_data)
        print(f"✅ تم التنفيذ: {order.id}")
        
        return {
            'order': order,
            'suggested_sl': suggested_sl,
            'suggested_tp': suggested_tp
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
    send_telegram_message(f"🤖 <b>بدء الفحص الشامل...</b>\n⏰ {datetime.now().strftime('%H:%M')}")
    
    alpaca_ok, alpaca_msg = test_alpaca_connection()
    print(f"حالة Alpaca: {alpaca_msg}")
    if not alpaca_ok:
        send_telegram_message(f"⚠️ <b>مشكلة في Alpaca:</b>\n{alpaca_msg}")
    
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
                
                if alert_key in last_alerts:
                    try:
                        last_time = datetime.fromisoformat(last_alerts[alert_key])
                        if (datetime.now() - last_time).total_seconds() < 43200:
                            print(f"️ تخطي {ticker} (تنبيه حديث)")
                            continue
                    except:
                        pass
                
                is_buy = "BUY" in result['signal']
                is_strong = "STRONG" in result['signal']
                emoji = "🟢" if is_buy else "🔴"
                action_text = "شراء" if is_buy else "بيع"
                strength_text = "قوية جداً" if is_strong else "متوسطة"
                
                message = f"""
{emoji} <b>إشارة {action_text} {strength_text}!</b>

📌 <b>{result['ticker']}</b>
💰 السعر: ${result['price']:.2f}
📊 RSI: {result['rsi']:.1f}
🛡️ الدعم: ${result['support']:.2f}
🚧 المقاومة: ${result['resistance']:.2f}
"""
                send_telegram_message(message)
                
                # التنفيذ التلقائي
                if is_strong and ticker in ALPACA_TRADABLE and alpaca_ok:
                    send_telegram_message(f"🤖 <b>جاري تنفيذ صفقة لـ {ticker}...</b>")
                    
                    result_trade, error = execute_trade_with_sl_tp(
                        ticker,
                        "buy" if is_buy else "sell",
                        result['price']
                    )
                    
                    if error:
                        errors_count += 1
                        send_telegram_message(f"❌ فشل تنفيذ {ticker}:\n{error[:200]}")
                    else:
                        trades_count += 1
                        entry = result_trade['entry_order']
                        sl = result_trade['stop_loss_order']
                        tp = result_trade['take_profit_order']
                        
                        success_msg = f"""
✅ <b>تم التنفيذ بنجاح!</b>

📌 الرمز: {ticker}
💰 سعر الدخول: ${result['price']:.2f}
🛑 وقف الخسارة: ${result_trade['stop_loss']:.2f} (-{STOP_LOSS_PERCENT}%)
🎯 جني الأرباح: ${result_trade['take_profit']:.2f} (+{TAKE_PROFIT_PERCENT}%)
📦 الكمية: {TRADE_QTY}

🔖 أمر الدخول: {entry.id}
 وقف الخسارة: {sl.id}
🔖 جني الأرباح: {tp.id}
"""
                        send_telegram_message(success_msg)
                
                new_alerts[alert_key] = datetime.now().isoformat()
        except Exception as e:
            errors_count += 1
            print(f"❌ خطأ في معالجة {ticker}: {e}")
            send_telegram_message(f"❌ خطأ في {ticker}:\n{str(e)[:150]}")
    
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
    
    if new_alerts:
        try:
            with open(ALERTS_FILE, 'w') as f:
                json.dump(new_alerts, f)
        except Exception as e:
            print(f"خطأ في حفظ التنبيهات: {e}")
    
    print(f"\n✅ انتهى الفحص - إشارات: {signals_count}, صفقات: {trades_count}, أخطاء: {errors_count}")

if __name__ == "__main__":
    main()
