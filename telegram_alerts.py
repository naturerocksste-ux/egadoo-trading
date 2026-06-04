import yfinance as yf
import pandas as pd
import requests
import json
import os
import time
from datetime import datetime

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

# ==========================================
# 2. الدوال المساعدة
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
            return None
        
        current_price = float(df['Close'].iloc[-1])
        support = float(df['Low'].rolling(20).min().iloc[-1])
        resistance = float(df['High'].rolling(20).max().iloc[-1])
        
        rsi_series = calculate_rsi(df)
        if rsi_series is None or rsi_series.empty:
            return None
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
            }
        return None
    except Exception as e:
        print(f"خطأ في {ticker}: {e}")
        return None

def test_alpaca():
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return False, "مفاتيح Alpaca غير متاحة"
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY, paper=True)
        account = client.get_account()
        return True, f"متصل! الرصيد: ${float(account.cash):,.2f}"
    except Exception as e:
        return False, f"فشل: {str(e)}"

def cleanup_and_verify(client):
    """تنظيف شامل مع التحقق من النجاح"""
    print("🧹 بدء التنظيف الشامل...")
    
    # 1. إلغاء جميع الأوامر
    print("  📋 إلغاء الأوامر المعلقة...")
    try:
        orders = client.get_orders(status='open')
        print(f"    وجدت {len(orders)} أمر معلق")
        if orders:
            client.cancel_all_orders()
            print("    ⏳ انتظار 5 ثوانٍ...")
            time.sleep(5)
            
            # التحقق من الإلغاء
            remaining_orders = client.get_orders(status='open')
            if len(remaining_orders) == 0:
                print("    ✅ تم إلغاء جميع الأوامر بنجاح")
            else:
                print(f"    ⚠️ لا تزال {len(remaining_orders)} أوامر معلقة")
                return False
        else:
            print("    ✅ لا توجد أوامر معلقة")
    except Exception as e:
        print(f"    ❌ خطأ في إلغاء الأوامر: {e}")
        return False
    
    # 2. إغلاق جميع المراكز
    print("  📊 إغلاق المراكز المفتوحة...")
    try:
        positions = client.get_all_positions()
        print(f"    وجدت {len(positions)} مركز مفتوح")
        if positions:
            for pos in positions:
                try:
                    print(f"    🔄 إغلاق {pos.symbol}...")
                    client.close_position(pos.symbol)
                    time.sleep(2)
                    print(f"    ✅ تم إغلاق {pos.symbol}")
                except Exception as e:
                    print(f"    ❌ فشل إغلاق {pos.symbol}: {e}")
            
            # انتظار إضافي
            time.sleep(3)
            
            # التحقق من الإغلاق
            remaining_positions = client.get_all_positions()
            if len(remaining_positions) == 0:
                print("    ✅ تم إغلاق جميع المراكز بنجاح")
            else:
                print(f"    ⚠️ لا تزال {len(remaining_positions)} مراكز مفتوحة")
                return False
        else:
            print("    ✅ لا توجد مراكز مفتوحة")
    except Exception as e:
        print(f"    ❌ خطأ في إغلاق المراكز: {e}")
        return False
    
    print("  ✅ اكتمل التنظيف بنجاح!")
    return True

def execute_trade(ticker, side, entry_price):
    """تنفيذ صفقة بعد التأكد من نظافة الحساب"""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None, "مفاتيح Alpaca غير متاحة"
    
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest, StopOrderRequest, LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=True
        )
        
        # تنظيف الحساب والتحقق
        print("🔹 خطوة 1: تنظيف الحساب...")
        if not cleanup_and_verify(client):
            return None, "فشل تنظيف الحساب. يرجى التنظيف يدوياً من Alpaca Dashboard."
        
        # حساب الأسعار
        if side == "buy":
            sl_price = round(entry_price * (1 - STOP_LOSS_PERCENT / 100), 2)
            tp_price = round(entry_price * (1 + TAKE_PROFIT_PERCENT / 100), 2)
            sl_side = OrderSide.SELL
            tp_side = OrderSide.SELL
        else:
            sl_price = round(entry_price * (1 + STOP_LOSS_PERCENT / 100), 2)
            tp_price = round(entry_price * (1 - TAKE_PROFIT_PERCENT / 100), 2)
            sl_side = OrderSide.BUY
            tp_side = OrderSide.BUY
        
        print(f"🔹 خطوة 2: تنفيذ أمر الدخول لـ {ticker}...")
        
        # أمر الدخول
        entry_order = MarketOrderRequest(
            symbol=ticker,
            qty=TRADE_QTY,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        entry_result = client.submit_order(order_data=entry_order)
        print(f"  ✅ أمر الدخول: {entry_result.id}")
        
        # انتظار التنفيذ
        print("  ⏳ انتظار 5 ثوانٍ...")
        time.sleep(5)
        
        # التحقق من التنفيذ
        order_status = client.get_order_by_id(entry_result.id)
        actual_price = float(order_status.filled_avg_price) if order_status.filled_avg_price else entry_price
        print(f"  ✅ تم التنفيذ بسعر: ${actual_price:.2f}")
        
        # إعادة حساب SL/TP
        if side == "buy":
            sl_price = round(actual_price * (1 - STOP_LOSS_PERCENT / 100), 2)
            tp_price = round(actual_price * (1 + TAKE_PROFIT_PERCENT / 100), 2)
        else:
            sl_price = round(actual_price * (1 + STOP_LOSS_PERCENT / 100), 2)
            tp_price = round(actual_price * (1 - TAKE_PROFIT_PERCENT / 100), 2)
        
        # Stop Loss
        print(f"🔹 خطوة 3: وضع Stop Loss عند ${sl_price}...")
        sl_order = StopOrderRequest(
            symbol=ticker,
            qty=TRADE_QTY,
            side=sl_side,
            stop_price=sl_price,
            time_in_force=TimeInForce.GTC
        )
        sl_result = client.submit_order(order_data=sl_order)
        print(f"  ✅ Stop Loss: {sl_result.id}")
        
        time.sleep(1)
        
        # Take Profit
        print(f"🔹 خطوة 4: وضع Take Profit عند ${tp_price}...")
        tp_order = LimitOrderRequest(
            symbol=ticker,
            qty=TRADE_QTY,
            side=tp_side,
            limit_price=tp_price,
            time_in_force=TimeInForce.GTC
        )
        tp_result = client.submit_order(order_data=tp_order)
        print(f"  ✅ Take Profit: {tp_result.id}")
        
        return {
            'entry': entry_result,
            'stop_loss': sl_result,
            'take_profit': tp_result,
            'actual_price': actual_price,
            'sl_price': sl_price,
            'tp_price': tp_price
        }, None
        
    except Exception as e:
        import traceback
        return None, f"{str(e)}\n\n{traceback.format_exc()}"

# ==========================================
# 3. المحرك الرئيسي
# ==========================================
def main():
    print(f"🤖 بدء الفحص - {datetime.now()}")
    send_telegram(f"🤖 <b>بدء الفحص الشامل...</b>\n {datetime.now().strftime('%H:%M')}")
    
    alpaca_ok, alpaca_msg = test_alpaca()
    print(f"Alpaca: {alpaca_msg}")
    if not alpaca_ok:
        send_telegram(f"⚠️ <b>مشكلة Alpaca:</b>\n{alpaca_msg}")
    
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
    
    for ticker in GLOBAL_WATCHLIST:
        print(f"\nفحص {ticker}...")
        try:
            result = analyze_stock(ticker)
            
            if result:
                signals += 1
                print(f"✅ إشارة: {result['signal']}")
                
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
                emoji = "" if is_buy else "🔴"
                action = "شراء" if is_buy else "بيع"
                strength = "قوية جداً" if is_strong else "متوسطة"
                
                msg = f"""
{emoji} <b>إشارة {action} {strength}!</b>

📌 <b>{result['ticker']}</b>
💰 السعر: ${result['price']:.2f}
📊 RSI: {result['rsi']:.1f}
🛡️ الدعم: ${result['support']:.2f}
🚧 المقاومة: ${result['resistance']:.2f}
"""
                send_telegram(msg)
                
                if is_strong and ticker in ALPACA_TRADABLE and alpaca_ok:
                    send_telegram(f"🤖 <b>جاري تنفيذ صفقة لـ {ticker}...</b>")
                    
                    trade_result, error = execute_trade(
                        ticker, "buy" if is_buy else "sell", result['price']
                    )
                    
                    if error:
                        errors += 1
                        send_telegram(f"❌ فشل {ticker}:\n{error[:200]}")
                    else:
                        trades += 1
                        success = f"""
✅ <b>تم التنفيذ بنجاح!</b>

📌 الرمز: {ticker}
💰 سعر الدخول: ${trade_result['actual_price']:.2f}
📦 الكمية: {TRADE_QTY}

🛡️ <b>الحماية التلقائية:</b>
🛑 وقف الخسارة: ${trade_result['sl_price']:.2f} (-{STOP_LOSS_PERCENT}%)
🎯 جني الأرباح: ${trade_result['tp_price']:.2f} (+{TAKE_PROFIT_PERCENT}%)

 أمر الدخول: {trade_result['entry'].id}
🛑 Stop Loss: {trade_result['stop_loss'].id}
🎯 Take Profit: {trade_result['take_profit'].id}

✨ الأوامر معلقة وستنفذ تلقائياً!
"""
                        send_telegram(success)
                
                new_alerts[alert_key] = datetime.now().isoformat()
        except Exception as e:
            errors += 1
            print(f"❌ خطأ في {ticker}: {e}")
            send_telegram(f"❌ خطأ في {ticker}:\n{str(e)[:150]}")
    
    summary = f"""
📊 <b>ملخص الفحص:</b>

✅ إشارات: {signals}
🤖 صفقات منفذة: {trades}
❌ أخطاء: {errors}
 Alpaca: {'متصل' if alpaca_ok else 'غير متصل'}
⚙️ SL={STOP_LOSS_PERCENT}%, TP={TAKE_PROFIT_PERCENT}%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    send_telegram(summary)
    
    if new_alerts:
        try:
            with open(ALERTS_FILE, 'w') as f:
                json.dump(new_alerts, f)
        except:
            pass
    
    print(f"\n✅ انتهى - إشارات: {signals}, صفقات: {trades}, أخطاء: {errors}")

if __name__ == "__main__":
    main()
