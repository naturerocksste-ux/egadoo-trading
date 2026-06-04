import os
import requests
import json
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient

# ==========================================
# 1. الإعدادات
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')

ALERTS_FILE = "last_alerts.json"

# ==========================================
# 2. دوال مساعدة
# ==========================================
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ مفاتيح تيليجرام غير متاحة")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"خطأ تيليجرام: {e}")
        return False

def get_alpaca_data():
    """جلب بيانات الحساب من Alpaca"""
    try:
        from alpaca.trading.requests import GetOrdersRequest
        
        client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=True
        )
        
        # معلومات الحساب
        account = client.get_account()
        portfolio_value = float(account.portfolio_value)
        cash = float(account.cash)
        equity = float(account.equity)
        
        # المراكز المفتوحة
        positions = client.get_all_positions()
        open_positions = []
        for pos in positions:
            open_positions.append({
                'symbol': pos.symbol,
                'qty': float(pos.qty),
                'side': pos.side,
                'current_price': float(pos.current_price),
                'avg_entry': float(pos.avg_entry_price),
                'market_value': float(pos.market_value),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc) * 100
            })
        
        # ✅ جلب جميع الأوامر (بدون filter)
        last_week = datetime.now() - timedelta(days=7)
        
        try:
            orders_filter = GetOrdersRequest(
                limit=100,
                until=datetime.now(),
                after=last_week
            )
            orders = client.get_orders(filter=orders_filter)
        except:
            # إذا فشل، جلب آخر 100 أمر
            orders = client.get_orders()
        
        # تصفية الأوامر المنفذة فقط
        filled_orders = [o for o in orders if o.status == 'filled']
        
        return {
            'portfolio_value': portfolio_value,
            'cash': cash,
            'equity': equity,
            'open_positions': open_positions,
            'filled_orders': filled_orders,
            'success': True
        }, None
        
    except Exception as e:
        return None, str(e)
        
def analyze_trades(filled_orders):
    """تحليل الصفقات المنفذة"""
    if not filled_orders:
        return {
            'total': 0,
            'buys': 0,
            'sells': 0,
            'symbols': {},
            'best_trade': None,
            'worst_trade': None
        }
    
    buys = [o for o in filled_orders if o.side == 'buy']
    sells = [o for o in filled_orders if o.side == 'sell']
    
    # حساب عدد الصفقات لكل سهم
    symbols = {}
    for order in filled_orders:
        if order.symbol not in symbols:
            symbols[order.symbol] = 0
        symbols[order.symbol] += 1
    
    # ترتيب الأسهم حسب عدد الصفقات
    sorted_symbols = sorted(symbols.items(), key=lambda x: x[1], reverse=True)
    
    # أفضل وأسوأ صفقة (بناءً على الكمية × السعر)
    trades_by_value = [(o, float(o.qty) * float(o.filled_avg_price or 0)) for o in filled_orders]
    trades_by_value.sort(key=lambda x: x[1], reverse=True)
    
    best_trade = trades_by_value[0] if trades_by_value else None
    worst_trade = trades_by_value[-1] if trades_by_value else None
    
    return {
        'total': len(filled_orders),
        'buys': len(buys),
        'sells': len(sells),
        'symbols': sorted_symbols[:5],  # Top 5
        'best_trade': best_trade,
        'worst_trade': worst_trade
    }

def generate_weekly_report():
    """إنشاء التقرير الأسبوعي"""
    print(f"📊 إنشاء التقرير الأسبوعي - {datetime.now()}")
    
    # جلب البيانات
    data, error = get_alpaca_data()
    if error:
        send_telegram(f"❌ <b>فشل إنشاء التقرير:</b>\n{error}")
        return
    
    # تحليل الصفقات
    trade_stats = analyze_trades(data['filled_orders'])
    
    # حساب الربح/الخسارة (مقارنة بالرصيد الابتدائي $100,000)
    initial_balance = 100000
    profit_loss = data['portfolio_value'] - initial_balance
    profit_loss_pct = (profit_loss / initial_balance) * 100
    
    # تنسيق الرسالة
    profit_emoji = "📈" if profit_loss >= 0 else "📉"
    profit_sign = "+" if profit_loss >= 0 else ""
    
    report = f"""
📊 <b>التقرير الأسبوعي</b>
📅 {datetime.now().strftime('%d/%m/%Y')}

━━━━━━━━━━━━━━━━━━━━

💰 <b>ملخص المحفظة:</b>
• الرصيد الحالي: ${data['portfolio_value']:,.2f}
• النقد المتاح: ${data['cash']:,.2f}
• {profit_emoji} الربح/الخسارة: {profit_sign}${profit_loss:,.2f} ({profit_sign}{profit_loss_pct:.2f}%)

━━━━━━━━━━━━━━━━━━━━

📋 <b>إحصائيات التداول (آخر 7 أيام):</b>
• عدد الأوامر المنفذة: {trade_stats['total']}
• أوامر شراء: {trade_stats['buys']}
• أوامر بيع: {trade_stats['sells']}
"""
    
    # أفضل وأسوأ صفقة
    if trade_stats['best_trade']:
        best_order, best_value = trade_stats['best_trade']
        report += f"• 💵 أكبر صفقة: {best_order.symbol} (${best_value:,.2f})\n"
    
    if trade_stats['worst_trade']:
        worst_order, worst_value = trade_stats['worst_trade']
        report += f"• 💸 أصغر صفقة: {worst_order.symbol} (${worst_value:,.2f})\n"
    
    report += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # الأسهم الأكثر تداولاً
    if trade_stats['symbols']:
        report += "📊 <b>الأسهم الأكثر تداولاً:</b>\n"
        for i, (symbol, count) in enumerate(trade_stats['symbols'], 1):
            report += f"{i}. {symbol} - {count} صفقة\n"
        report += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # المراكز المفتوحة
    if data['open_positions']:
        report += " <b>المراكز المفتوحة حالياً:</b>\n"
        for pos in data['open_positions']:
            pl_emoji = "🟢" if pos['unrealized_pl'] >= 0 else "🔴"
            pl_sign = "+" if pos['unrealized_pl'] >= 0 else ""
            report += f"• {pos['symbol']}: {pos['qty']} سهم ({pos['side']})\n"
            report += f"  {pl_emoji} الربح/الخسارة: {pl_sign}${pos['unrealized_pl']:,.2f} ({pl_sign}{pos['unrealized_plpc']:.2f}%)\n\n"
    else:
        report += "📌 <b>لا توجد مراكز مفتوحة حالياً</b>\n\n"
    
    report += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # توصيات بسيطة
    report += "🎯 <b>توصيات عامة:</b>\n"
    report += "• راجع أداء البوت يومياً\n"
    report += "• لا تتداول بعاطفة\n"
    report += "• استخدم وقف الخسارة دائماً\n"
    report += "• السهم الأفضل أداءً هذا الأسبوع يستحق المتابعة\n\n"
    
    # موعد التقرير التالي
    next_report = datetime.now() + timedelta(days=7)
    report += f"⏰ <b>التقرير التالي:</b> {next_report.strftime('%d/%m/%Y')}\n\n"
    report += "━━━━━━━━━━━━━━━━━━━━\n"
    report += f"<i>تم الإنشاء بواسطة بوت التداول الآلي</i>\n"
    report += f"<i>{datetime.now().strftime('%H:%M:%S')}</i>"
    
    # إرسال التقرير
    send_telegram(report)
    print("✅ تم إرسال التقرير الأسبوعي")

# ==========================================
# 3. التشغيل
# ==========================================
if __name__ == "__main__":
    generate_weekly_report()
