import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime, timedelta

# ==========================================
# 1. الإعدادات
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# أسهم نشطة للخيارات
OPTIONS_SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY", "META", "GOOGL"]

# ==========================================
# 2. دوال مساعدة
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

def scan_options_for_symbol(symbol):
    """فحص خيارات السهم"""
    try:
        stock = yf.Ticker(symbol)
        expirations = stock.options
        
        if not expirations:
            return None
        
        # اختيار أقرب تاريخ انتهاء
        expiration = expirations[0]
        chain = stock.option_chain(expiration)
        
        calls = chain.calls
        puts = chain.puts
        
        if calls.empty or puts.empty:
            return None
        
        current_price = float(stock.info.get('currentPrice', 0))
        if current_price == 0:
            return None
        
        # البحث عن Calls ITM (In The Money) مع حجم عالي
        calls_itm = calls[calls['strike'] <= current_price * 1.05]
        calls_high_volume = calls_itm[calls_itm['volume'] > calls_itm['volume'].median()]
        
        # البحث عن Puts ITM مع حجم عالي
        puts_itm = puts[puts['strike'] >= current_price * 0.95]
        puts_high_volume = puts_itm[puts_itm['volume'] > puts_itm['volume'].median()]
        
        # اختيار أفضل فرصة Call
        best_call = None
        if not calls_high_volume.empty:
            best_call = calls_high_volume.loc[calls_high_volume['volume'].idxmax()]
        
        # اختيار أفضل فرصة Put
        best_put = None
        if not puts_high_volume.empty:
            best_put = puts_high_volume.loc[puts_high_volume['volume'].idxmax()]
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'expiration': expiration,
            'best_call': best_call,
            'best_put': best_put,
            'total_calls': len(calls),
            'total_puts': len(puts)
        }
    except Exception as e:
        print(f"خطأ في {symbol}: {e}")
        return None

def generate_options_report():
    """إنشاء تقرير الخيارات اليومي"""
    print(f" فحص الخيارات - {datetime.now()}")
    
    send_telegram(f" <b>فحص الخيارات اليومي</b>\n⏰ {datetime.now().strftime('%H:%M')}")
    
    opportunities = []
    
    for symbol in OPTIONS_SYMBOLS:
        print(f"فحص {symbol}...")
        result = scan_options_for_symbol(symbol)
        
        if result:
            opportunities.append(result)
    
    if not opportunities:
        send_telegram("️ لم يتم العثور على فرص خيارات اليوم.")
        return
    
    # بناء الرسالة
    report = f"""
📊 <b>فرص الخيارات اليوم</b>
📅 {datetime.now().strftime('%d/%m/%Y')}

━━━━━━━━━━━━━━━━━━━━
"""
    
    for opp in opportunities[:5]:  # أفضل 5 فقط
        report += f"\n<b>📌 {opp['symbol']}</b> - ${opp['current_price']:.2f}\n"
        report += f" انتهاء: {opp['expiration']}\n"
        
        if opp['best_call'] is not None:
            call = opp['best_call']
            report += f"🟢 <b>Call فرصة:</b>\n"
            report += f"   Strike: ${call['strike']:.2f}\n"
            report += f"   Last Price: ${call['lastPrice']:.2f}\n"
            report += f"   Volume: {int(call['volume'])}\n"
            report += f"   Open Interest: {int(call['openInterest'])}\n"
        
        if opp['best_put'] is not None:
            put = opp['best_put']
            report += f"🔴 <b>Put فرصة:</b>\n"
            report += f"   Strike: ${put['strike']:.2f}\n"
            report += f"   Last Price: ${put['lastPrice']:.2f}\n"
            report += f"   Volume: {int(put['volume'])}\n"
            report += f"   Open Interest: {int(put['openInterest'])}\n"
        
        report += "━━━━━━━━━━━━━━━━━━━━\n"
    
    report += """
⚠️ <b>تنبيه مهم:</b>
• الخيارات معقدة وخطيرة
• لا تتداول إلا إذا فهمت المخاطر
• استشر خبيراً مالياً قبل التداول
• هذا التقرير للمراقبة فقط

📚 <b>تعلم الخيارات:</b>
• Investopedia Options Basics
• CBOE Education
"""
    
    send_telegram(report)
    print("✅ تم إرسال تقرير الخيارات")

if __name__ == "__main__":
    generate_options_report()
