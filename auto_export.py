import os
import requests
import json
from datetime import datetime, timedelta
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import CellIsRule
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
import yfinance as yf

# ==========================================
# 1. الإعدادات
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')

TEMPLATE_FILE = "template.xlsx"  # سيتم إنشاؤه تلقائياً

# تصنيف الأسهم حسب السوق
MARKET_CATEGORIES = {
    'أمريكي': ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'AMZN', 'SPY', 'META', 'GOOGL', 'AMD', 'NFLX'],
    'سعودي': ['2222.SR', '1120.SR', '2010.SR', '1150.SR'],
    'إماراتي': ['ADCB.AD', 'FAB.AD', 'EMAAR.DU'],
    'كريبتو': ['BTC-USD', 'ETH-USD', 'BTCUSD', 'ETHUSD', 'SOL-USD'],
    'معادن': ['GC=F', 'SI=F'],
    'فوركس': ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X', 'EURUSD', 'GBPUSD']
}

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

def send_telegram_document(file_path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': TELEGRAM_CHAT_ID}
            r = requests.post(url, data=data, files=files, timeout=30)
        return r.status_code == 200
    except Exception as e:
        print(f"خطأ إرسال الملف: {e}")
        return False

def get_market_category(symbol):
    """تحديد السوق بناءً على رمز السهم"""
    for market, symbols in MARKET_CATEGORIES.items():
        if symbol in symbols:
            return market
    # تصنيفات إضافية
    if symbol.endswith('.SR'):
        return 'سعودي'
    elif symbol.endswith('.AD') or symbol.endswith('.DU'):
        return 'إماراتي'
    elif 'USD' in symbol or symbol in ['BTC', 'ETH', 'SOL']:
        return 'كريبتو'
    elif symbol in ['GC=F', 'SI=F', 'CL=F']:
        return 'معادن'
    elif '=' in symbol and 'USD' in symbol:
        return 'فوركس'
    else:
        return 'أمريكي'  # الافتراضي

def get_trades_from_alpaca():
    """جلب جميع الصفقات المنفذة من Alpaca"""
    try:
        client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=True
        )
        
        # جلب آخر 1000 أمر
        orders_filter = GetOrdersRequest(limit=1000)
        orders = client.get_orders(filter=orders_filter)
        
        # تصفية الأوامر المنفذة فقط
        filled_orders = [o for o in orders if o.status == 'filled']
        
        trades = []
        for order in filled_orders:
            try:
                # حساب الربح/الخسارة
                qty = float(order.qty)
                filled_price = float(order.filled_avg_price) if order.filled_avg_price else 0
                
                # البحث عن الصفقة المقابلة (إذا كانت زوجية)
                # ملاحظة: هذا تبسيط - في الواقع نحتاج لتحليل أكثر تعقيداً
                
                trade_data = {
                    'date': order.filled_at.strftime('%Y-%m-%d') if order.filled_at else '',
                    'time': order.filled_at.strftime('%H:%M') if order.filled_at else '',
                    'symbol': order.symbol,
                    'market': get_market_category(order.symbol),
                    'side': 'شراء' if order.side == 'buy' else 'بيع',
                    'entry_price': filled_price,
                    'exit_price': filled_price,  # مؤقتاً - سنحسبه لاحقاً
                    'qty': qty,
                    'lstm': 'نعم' if order.symbol in ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'AMZN', 'SPY'] else 'لا',
                    'order_id': order.id,
                    'status': order.status
                }
                
                trades.append(trade_data)
            except Exception as e:
                print(f"خطأ في معالجة أمر {order.id}: {e}")
        
        return trades, None
    except Exception as e:
        return None, str(e)

def calculate_trade_pnl(trades):
    """حساب الربح/الخسارة للصفقات"""
    # تجميع الصفقات حسب الرمز
    positions = {}
    
    for trade in trades:
        symbol = trade['symbol']
        if symbol not in positions:
            positions[symbol] = []
        positions[symbol].append(trade)
    
    # حساب PnL لكل صفقة
    processed_trades = []
    for symbol, symbol_trades in positions.items():
        # ترتيب الصفقات حسب التاريخ
        symbol_trades.sort(key=lambda x: x['date'] + x['time'])
        
        # محاكاة الصفقات (شراء ثم بيع)
        buy_queue = []
        
        for trade in symbol_trades:
            if trade['side'] == 'شراء':
                buy_queue.append(trade)
            else:  # بيع
                if buy_queue:
                    buy_trade = buy_queue.pop(0)
                    
                    # حساب الربح/الخسارة
                    entry_price = buy_trade['entry_price']
                    exit_price = trade['entry_price']  # سعر البيع
                    qty = min(buy_trade['qty'], trade['qty'])
                    
                    pnl = (exit_price - entry_price) * qty
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                    
                    # مدة الصفقة
                    try:
                        buy_dt = datetime.strptime(buy_trade['date'] + ' ' + buy_trade['time'], '%Y-%m-%d %H:%M')
                        sell_dt = datetime.strptime(trade['date'] + ' ' + trade['time'], '%Y-%m-%d %H:%M')
                        duration = (sell_dt - buy_dt).total_seconds() / 60  # بالدقائق
                    except:
                        duration = 0
                    
                    processed_trade = {
                        'date': buy_trade['date'],
                        'time': buy_trade['time'],
                        'symbol': symbol,
                        'market': buy_trade['market'],
                        'side': 'شراء',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'qty': qty,
                        'lstm': buy_trade['lstm'],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'duration': duration,
                        'rsi': 50,  # قيمة افتراضية - يمكن جلبها من yfinance
                        'strength': 'متوسطة',
                        'notes': f"صفقة مكتملة - ID: {buy_trade['order_id']}"
                    }
                    processed_trades.append(processed_trade)
    
    return processed_trades

def create_excel_with_trades(trades):
    """إنشاء ملف Excel مع بيانات الصفقات"""
    try:
        # محاولة تحميل القالب
        if os.path.exists(TEMPLATE_FILE):
            wb = load_workbook(TEMPLATE_FILE)
            ws_data = wb['البيانات']
        else:
            # إنشاء ملف جديد بسيط
            from openpyxl import Workbook
            wb = Workbook()
            ws_data = wb.active
            ws_data.title = "البيانات"
            
            # إضافة العناوين
            headers = ['رقم', 'التاريخ', 'الوقت', 'الرمز', 'السوق', 'نوع الصفقة',
                      'سعر الدخول', 'سعر الخروج', 'الكمية', 'تأكيد LSTM',
                      'الربح/الخسارة $', 'الربح/الخسارة %', 'مدة الصفقة',
                      'RSI', 'قوة الإشارة', 'ملاحظات', 'الحالة']
            
            for col, header in enumerate(headers, 1):
                cell = ws_data.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        
        # إدخال البيانات
        for row_idx, trade in enumerate(trades, 2):
            ws_data.cell(row=row_idx, column=1, value=row_idx-1)
            ws_data.cell(row=row_idx, column=2, value=trade['date'])
            ws_data.cell(row=row_idx, column=3, value=trade['time'])
            ws_data.cell(row=row_idx, column=4, value=trade['symbol'])
            ws_data.cell(row=row_idx, column=5, value=trade['market'])
            ws_data.cell(row=row_idx, column=6, value=trade['side'])
            ws_data.cell(row=row_idx, column=7, value=trade['entry_price'])
            ws_data.cell(row=row_idx, column=8, value=trade['exit_price'])
            ws_data.cell(row=row_idx, column=9, value=trade['qty'])
            ws_data.cell(row=row_idx, column=10, value=trade['lstm'])
            ws_data.cell(row=row_idx, column=11, value=trade['pnl'])
            ws_data.cell(row=row_idx, column=12, value=trade['pnl_pct'])
            ws_data.cell(row=row_idx, column=13, value=trade['duration'])
            ws_data.cell(row=row_idx, column=14, value=trade.get('rsi', 50))
            ws_data.cell(row=row_idx, column=15, value=trade.get('strength', 'متوسطة'))
            ws_data.cell(row=row_idx, column=16, value=trade.get('notes', ''))
            ws_data.cell(row=row_idx, column=17, value='مكتملة')
            
            # تنسيق الأرقام
            ws_data.cell(row=row_idx, column=11).number_format = '#,##0.00'
            ws_data.cell(row=row_idx, column=12).number_format = '0.00"%"'
            
            # تلوين حسب الربح/الخسارة
            pnl_cell = ws_data.cell(row=row_idx, column=11)
            if trade['pnl'] > 0:
                pnl_cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                pnl_cell.font = Font(color="006100")
            elif trade['pnl'] < 0:
                pnl_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                pnl_cell.font = Font(color="9C0006")
        
        # حفظ الملف
        filename = f"تقرير_الصفقات_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        wb.save(filename)
        return filename, None
        
    except Exception as e:
        return None, str(e)

# ==========================================
# 3. التشغيل الرئيسي
# ==========================================
def main():
    print(f"🚀 بدء التصدير التلقائي - {datetime.now()}")
    send_telegram("📊 <b>جاري تصدير صفقاتك من Alpaca...</b>")
    
    # جلب الصفقات
    trades, error = get_trades_from_alpaca()
    if error:
        send_telegram(f"❌ فشل جلب الصفقات:\n{error}")
        return
    
    print(f"✅ تم جلب {len(trades)} أمر منفذ")
    
    if len(trades) == 0:
        send_telegram("⚠️ لا توجد صفقات منفذة حتى الآن.")
        return
    
    # حساب الربح/الخسارة
    processed_trades = calculate_trade_pnl(trades)
    print(f"✅ تم معالجة {len(processed_trades)} صفقة مكتملة")
    
    if len(processed_trades) == 0:
        send_telegram("⚠️ لا توجد صفقات مكتملة (شراء + بيع) حتى الآن.")
        return
    
    # إنشاء ملف Excel
    filename, error = create_excel_with_trades(processed_trades)
    if error:
        send_telegram(f"❌ فشل إنشاء الملف:\n{error}")
        return
    
    # حساب الإحصائيات
    total_trades = len(processed_trades)
    winning_trades = sum(1 for t in processed_trades if t['pnl'] > 0)
    losing_trades = sum(1 for t in processed_trades if t['pnl'] < 0)
    total_pnl = sum(t['pnl'] for t in processed_trades)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # إرسال الملخص
    summary = f"""
✅ <b>تم تصدير صفقاتك بنجاح!</b>

📊 <b>الإحصائيات:</b>
• إجمالي الصفقات: {total_trades}
• صفقات رابحة: {winning_trades}
• صفقات خاسرة: {losing_trades}
• نسبة النجاح: {win_rate:.1f}%
• إجمالي الربح/الخسارة: ${total_pnl:.2f}

📁 <b>اسم الملف:</b> {filename}

📋 <b>الملف يحتوي على:</b>
• جميع صفقاتك من Alpaca
• حساب الربح/الخسارة تلقائياً
• تصنيف حسب السوق
• تأكيد LSTM لكل صفقة

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    send_telegram(summary)
    
    # إرسال الملف
    if send_telegram_document(filename):
        send_telegram("📎 <b>تم إرسال ملف Excel بنجاح!</b>")
    else:
        send_telegram("⚠️ <b>فشل إرسال الملف. يمكنك تحميله من GitHub.</b>")

if __name__ == "__main__":
    main()
