import os
import requests
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.chart import BarChart, PieChart, LineChart, Reference
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule

# ==========================================
# 1. الإعدادات
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

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

# ==========================================
# 3. أنماط التنسيق
# ==========================================
# الألوان
DARK_BLUE = "1F4E79"
LIGHT_BLUE = "D6E4F0"
GREEN = "C6EFCE"
RED = "FFC7CE"
YELLOW = "FFEB9C"
ORANGE = "F4B084"
PURPLE = "B4A7D6"

# الخطوط
title_font = Font(name='Calibri', size=18, bold=True, color="FFFFFF")
header_font = Font(name='Calibri', size=11, bold=True, color="FFFFFF")
subheader_font = Font(name='Calibri', size=12, bold=True, color=DARK_BLUE)
normal_font = Font(name='Calibri', size=11)
bold_font = Font(name='Calibri', size=11, bold=True)
green_font = Font(name='Calibri', size=11, color="006100")
red_font = Font(name='Calibri', size=11, color="9C0006")
big_number_font = Font(name='Calibri', size=24, bold=True, color=DARK_BLUE)

# الخلفيات
title_fill = PatternFill(start_color=DARK_BLUE, end_color=DARK_BLUE, fill_type="solid")
header_fill = PatternFill(start_color=DARK_BLUE, end_color=DARK_BLUE, fill_type="solid")
light_blue_fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
green_fill = PatternFill(start_color=GREEN, end_color=GREEN, fill_type="solid")
red_fill = PatternFill(start_color=RED, end_color=RED, fill_type="solid")
yellow_fill = PatternFill(start_color=YELLOW, end_color=YELLOW, fill_type="solid")

# المحاذاة
center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
left_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
right_align = Alignment(horizontal='right', vertical='center')

# الحدود
thin_border = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)

# ==========================================
# 4. إنشاء القالب
# ==========================================
def create_performance_template():
    """إنشاء قالب Excel احترافي لتقييم الأداء"""
    print(f"📊 إنشاء قالب تقييم الأداء - {datetime.now()}")
    
    wb = Workbook()
    wb.remove(wb.active)
    
    # ==========================================
    # Sheet 1: البيانات (بيانات الصفقات)
    # ==========================================
    ws_data = wb.create_sheet("البيانات")
    
    # العنوان
    ws_data.merge_cells('A1:Q1')
    title_cell = ws_data['A1']
    title_cell.value = "سجل الصفقات - أدخل بياناتك هنا"
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = center_align
    ws_data.row_dimensions[1].height = 40
    
    # التعليمات
    ws_data.merge_cells('A2:Q2')
    instruction = ws_data['A2']
    instruction.value = "⚠️ تعليمات: أدخل بيانات كل صفقة في صف جديد. الأعمدة B-P ستُحسب تلقائياً!"
    instruction.font = Font(name='Calibri', size=11, bold=True, color="C00000")
    instruction.alignment = center_align
    ws_data.row_dimensions[2].height = 25
    
    # العناوين
    headers = [
        'رقم', 'التاريخ', 'الوقت', 'الرمز', 'السوق', 'نوع الصفقة',
        'سعر الدخول', 'سعر الخروج', 'الكمية', 'تأكيد LSTM',
        'الربح/الخسارة $', 'الربح/الخسارة %', 'مدة الصفقة (دقيقة)',
        'RSI عند الدخول', 'قوة الإشارة', 'ملاحظات', 'الحالة'
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws_data.cell(row=3, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    ws_data.row_dimensions[3].height = 30
    
    # صفوف البيانات الفارغة مع معادلات (100 صف)
    for row in range(4, 104):
        # رقم الصفقة
        ws_data.cell(row=row, column=1, value=row-3).border = thin_border
        ws_data.cell(row=row, column=1).alignment = center_align
        
        # الأعمدة التي يدخلها المستخدم (B-I)
        for col in range(2, 10):
            cell = ws_data.cell(row=row, column=col)
            cell.border = thin_border
            cell.alignment = center_align
        
        # معادلة الربح/الخسارة $ (K)
        # =IF(OR(G{row}="",H{row}="",I{row}=""),"",IF(F{row}="شراء",(H{row}-G{row})*I{row},(G{row}-H{row})*I{row}))
        formula_k = f'=IF(OR(G{row}="",H{row}="",I{row}=""),"",IF(F{row}="شراء",(H{row}-G{row})*I{row},(G{row}-H{row})*I{row}))'
        ws_data.cell(row=row, column=11, value=formula_k).border = thin_border
        ws_data.cell(row=row, column=11).alignment = center_align
        ws_data.cell(row=row, column=11).number_format = '#,##0.00'
        
        # معادلة الربح/الخسارة % (L)
        # =IF(OR(G{row}="",H{row}=""),"",IF(F{row}="شراء",(H{row}-G{row})/G{row}*100,(G{row}-H{row})/G{row}*100))
        formula_l = f'=IF(OR(G{row}="",H{row}=""),"",IF(F{row}="شراء",(H{row}-G{row})/G{row}*100,(G{row}-H{row})/G{row}*100))'
        ws_data.cell(row=row, column=12, value=formula_l).border = thin_border
        ws_data.cell(row=row, column=12).alignment = center_align
        ws_data.cell(row=row, column=12).number_format = '0.00"%"'
        
        # معادلة مدة الصفقة (M)
        # =IF(OR(B{row}="",C{row}=""),"",NOW()-(B{row}+C{row}))*1440
        formula_m = f'=IF(OR(B{row}="",C{row}=""),"",(NOW()-(B{row}+C{row}))*1440)'
        ws_data.cell(row=row, column=13, value=formula_m).border = thin_border
        ws_data.cell(row=row, column=13).alignment = center_align
        ws_data.cell(row=row, column=13).number_format = '0.0'
        
        # باقي الأعمدة (N-Q)
        for col in range(14, 18):
            ws_data.cell(row=row, column=col).border = thin_border
            ws_data.cell(row=row, column=col).alignment = center_align
    
    # عرض الأعمدة
    column_widths = [6, 12, 10, 10, 12, 12, 12, 12, 10, 12, 14, 14, 16, 12, 12, 20, 10]
    for i, width in enumerate(column_widths, 1):
        ws_data.column_dimensions[get_column_letter(i)].width = width
    
    # تنسيق شرطي للأرباح/الخسائر
    ws_data.conditional_formatting.add(
        'K4:K103',
        CellIsRule(operator='greaterThan', formula=['0'], fill=green_fill, font=green_font)
    )
    ws_data.conditional_formatting.add(
        'K4:K103',
        CellIsRule(operator='lessThan', formula=['0'], fill=red_fill, font=red_font)
    )
    ws_data.conditional_formatting.add(
        'L4:L103',
        CellIsRule(operator='greaterThan', formula=['0'], fill=green_fill, font=green_font)
    )
    ws_data.conditional_formatting.add(
        'L4:L103',
        CellIsRule(operator='lessThan', formula=['0'], fill=red_fill, font=red_font)
    )
    
    # تجميد الصفوف
    ws_data.freeze_panes = 'A4'
    
    # ==========================================
    # Sheet 2: التحليل التلقائي
    # ==========================================
    ws_analysis = wb.create_sheet("التحليل")
    
    # العنوان
    ws_analysis.merge_cells('A1:F1')
    ws_analysis['A1'].value = "لوحة التحكم - التحليل التلقائي"
    ws_analysis['A1'].font = title_font
    ws_analysis['A1'].fill = title_fill
    ws_analysis['A1'].alignment = center_align
    ws_analysis.row_dimensions[1].height = 40
    
    # === قسم المؤشرات الرئيسية ===
    ws_analysis.merge_cells('A3:F3')
    ws_analysis['A3'].value = "📊 المؤشرات الرئيسية"
    ws_analysis['A3'].font = subheader_font
    ws_analysis['A3'].alignment = left_align
    
    # جدول المؤشرات
    kpis = [
        ('إجمالي الصفقات', '=COUNTA(البيانات!B4:B103)-COUNTBLANK(البيانات!B4:B103)'),
        ('الصفقات الرابحة', '=COUNTIF(البيانات!K4:K103,">0")'),
        ('الصفقات الخاسرة', '=COUNTIF(البيانات!K4:K103,"<0")'),
        ('صفقات التعادل', '=COUNTIF(البيانات!K4:K103,"=0")-COUNTBLANK(البيانات!K4:K103)+COUNTA(البيانات!K4:K103)-COUNTIF(البيانات!K4:K103,">0")-COUNTIF(البيانات!K4:K103,"<0")'),
        ('', ''),
        ('نسبة النجاح %', '=IF(B4=0,0,B5/B4*100)'),
        ('إجمالي الربح/الخسارة $', '=SUM(البيانات!K4:K103)'),
        ('متوسط الربح $', '=IFERROR(AVERAGEIF(البيانات!K4:K103,">0"),0)'),
        ('متوسط الخسارة $', '=IFERROR(AVERAGEIF(البيانات!K4:K103,"<0"),0)'),
        ('نسبة Risk/Reward', '=IFERROR(ABS(B11/B12),0)'),
        ('', ''),
        ('أفضل صفقة $', '=IFERROR(MAX(البيانات!K4:K103),0)'),
        ('أسوأ صفقة $', '=IFERROR(MIN(البيانات!K4:K103),0)'),
        ('أكبر ربح %', '=IFERROR(MAX(البيانات!L4:L103),0)'),
        ('أكبر خسارة %', '=IFERROR(MIN(البيانات!L4:L103),0)'),
        ('متوسط مدة الصفقة (دقيقة)', '=IFERROR(AVERAGE(البيانات!M4:M103),0)'),
    ]
    
    row = 4
    for label, formula in kpis:
        if label == '':
            row += 1
            continue
        
        # اسم المؤشر
        ws_analysis.cell(row=row, column=1, value=label).font = bold_font
        ws_analysis.cell(row=row, column=1).alignment = left_align
        ws_analysis.cell(row=row, column=1).border = thin_border
        ws_analysis.cell(row=row, column=1).fill = light_blue_fill
        
        # القيمة
        value_cell = ws_analysis.cell(row=row, column=2, value=formula)
        value_cell.font = big_number_font if label == 'نسبة النجاح %' else bold_font
        value_cell.alignment = center_align
        value_cell.border = thin_border
        
        # تنسيق الأرقام
        if '%' in label:
            value_cell.number_format = '0.00'
        elif '$' in label:
            value_cell.number_format = '#,##0.00'
        
        row += 1
    
    # === قسم التقييم ===
    ws_analysis.merge_cells(f'A{row+1}:F{row+1}')
    ws_analysis[f'A{row+1}'].value = "🎯 التقييم العام"
    ws_analysis[f'A{row+1}'].font = subheader_font
    
    eval_start = row + 2
    evaluations = [
        ('تقييم نسبة النجاح', '=IF(B7>=60,"ممتاز ✅",IF(B7>=50,"جيد ✅",IF(B7>=40,"مقبول ⚠️","ضعيف ❌")))'),
        ('تقييم Risk/Reward', '=IF(B13>=2,"ممتاز ✅",IF(B13>=1.5,"جيد ✅",IF(B13>=1,"مقبول ⚠️","ضعيف ❌")))'),
        ('التقييم النهائي', '=IF(AND(B7>=50,B13>=1.5),"البوت يعمل بشكل جيد! استمر ✅","يحتاج تحسين ⚠️")'),
    ]
    
    for i, (label, formula) in enumerate(evaluations):
        ws_analysis.cell(row=eval_start+i, column=1, value=label).font = bold_font
        ws_analysis.cell(row=eval_start+i, column=1).border = thin_border
        ws_analysis.cell(row=eval_start+i, column=1).fill = light_blue_fill
        
        value_cell = ws_analysis.cell(row=eval_start+i, column=2, value=formula)
        value_cell.font = Font(name='Calibri', size=12, bold=True)
        value_cell.alignment = center_align
        value_cell.border = thin_border
    
    # عرض الأعمدة
    ws_analysis.column_dimensions['A'].width = 30
    ws_analysis.column_dimensions['B'].width = 25
    ws_analysis.column_dimensions['C'].width = 15
    
    # ==========================================
    # Sheet 3: تحليل LSTM
    # ==========================================
    ws_lstm = wb.create_sheet("تحليل LSTM")
    
    ws_lstm.merge_cells('A1:E1')
    ws_lstm['A1'].value = "🧠 تحليل فعالية الذكاء الاصطناعي LSTM"
    ws_lstm['A1'].font = title_font
    ws_lstm['A1'].fill = title_fill
    ws_lstm['A1'].alignment = center_align
    ws_lstm.row_dimensions[1].height = 40
    
    # جدول المقارنة
    ws_lstm['A3'] = "المجموعة"
    ws_lstm['B3'] = "عدد الصفقات"
    ws_lstm['C3'] = "الرابحة"
    ws_lstm['D3'] = "نسبة النجاح %"
    ws_lstm['E3'] = "متوسط الربح $"
    
    for col in range(1, 6):
        cell = ws_lstm.cell(row=3, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    # صف LSTM مؤكد
    ws_lstm['A4'] = "مؤكدة بـ LSTM ✅"
    ws_lstm['B4'] = '=COUNTIF(البيانات!J4:J103,"نعم")'
    ws_lstm['C4'] = '=COUNTIFS(البيانات!J4:J103,"نعم",البيانات!K4:K103,">0")'
    ws_lstm['D4'] = '=IFERROR(C4/B4*100,0)'
    ws_lstm['E4'] = '=IFERROR(AVERAGEIFS(البيانات!K4:K103,البيانات!J4:J103,"نعم"),0)'
    
    # صف عادية
    ws_lstm['A5'] = "صفقات عادية"
    ws_lstm['B5'] = '=COUNTIF(البيانات!J4:J103,"لا")'
    ws_lstm['C5'] = '=COUNTIFS(البيانات!J4:J103,"لا",البيانات!K4:K103,">0")'
    ws_lstm['D5'] = '=IFERROR(C5/B5*100,0)'
    ws_lstm['E5'] = '=IFERROR(AVERAGEIFS(البيانات!K4:K103,البيانات!J4:J103,"لا"),0)'
    
    # صف التحسين
    ws_lstm['A6'] = "التحسين بـ LSTM"
    ws_lstm['B6'] = ""
    ws_lstm['C6'] = ""
    ws_lstm['D6'] = '=D4-D5'
    ws_lstm['E6'] = '=E4-E5'
    
    for row in range(4, 7):
        for col in range(1, 6):
            cell = ws_lstm.cell(row=row, column=col)
            cell.border = thin_border
            cell.alignment = center_align
            if col in [4, 5]:
                cell.number_format = '0.00'
            if row == 6:
                cell.font = bold_font
                cell.fill = yellow_fill
    
    # التقييم
    ws_lstm['A8'] = "تقييم فعالية LSTM:"
    ws_lstm['A8'].font = subheader_font
    ws_lstm['B8'] = '=IF(D6>15,"ممتاز - LSTM يضيف قيمة كبيرة ✅",IF(D6>5,"جيد - LSTM مفيد ✅",IF(D6>0,"محايد ⚠️","سلبي - LSTM يقلل الدقة ❌")))'
    ws_lstm['B8'].font = Font(name='Calibri', size=12, bold=True)
    ws_lstm.merge_cells('B8:E8')
    
    # عرض الأعمدة
    for col in ['A', 'B', 'C', 'D', 'E']:
        ws_lstm.column_dimensions[col].width = 20
    
    # ==========================================
    # Sheet 4: تحليل الأسواق
    # ==========================================
    ws_markets = wb.create_sheet("تحليل الأسواق")
    
    ws_markets.merge_cells('A1:F1')
    ws_markets['A1'].value = "🌍 تحليل الأداء حسب السوق"
    ws_markets['A1'].font = title_font
    ws_markets['A1'].fill = title_fill
    ws_markets['A1'].alignment = center_align
    ws_markets.row_dimensions[1].height = 40
    
    # العناوين
    market_headers = ['السوق', 'عدد الصفقات', 'الرابحة', 'الخاسرة', 'نسبة النجاح %', 'إجمالي الربح $']
    for col, header in enumerate(market_headers, 1):
        cell = ws_markets.cell(row=3, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    # الأسواق
    markets = ['أمريكي', 'سعودي', 'إماراتي', 'كريبتو', 'معادن', 'فوركس']
    
    for i, market in enumerate(markets, 4):
        ws_markets.cell(row=i, column=1, value=market).border = thin_border
        ws_markets.cell(row=i, column=2, value=f'=COUNTIF(البيانات!E4:E103,"{market}")').border = thin_border
        ws_markets.cell(row=i, column=3, value=f'=COUNTIFS(البيانات!E4:E103,"{market}",البيانات!K4:K103,">0")').border = thin_border
        ws_markets.cell(row=i, column=4, value=f'=COUNTIFS(البيانات!E4:E103,"{market}",البيانات!K4:K103,"<0")').border = thin_border
        ws_markets.cell(row=i, column=5, value=f'=IFERROR(C{i}/B{i}*100,0)').border = thin_border
        ws_markets.cell(row=i, column=5).number_format = '0.00'
        ws_markets.cell(row=i, column=6, value=f'=SUMIF(البيانات!E4:E103,"{market}",البيانات!K4:K103)').border = thin_border
        ws_markets.cell(row=i, column=6).number_format = '#,##0.00'
        
        for col in range(1, 7):
            ws_markets.cell(row=i, column=col).alignment = center_align
    
    # صف الإجمالي
    ws_markets.cell(row=10, column=1, value="الإجمالي").font = bold_font
    ws_markets.cell(row=10, column=2, value="=SUM(B4:B9)").font = bold_font
    ws_markets.cell(row=10, column=3, value="=SUM(C4:C9)").font = bold_font
    ws_markets.cell(row=10, column=4, value="=SUM(D4:D9)").font = bold_font
    ws_markets.cell(row=10, column=5, value="=IFERROR(C10/B10*100,0)").font = bold_font
    ws_markets.cell(row=10, column=5).number_format = '0.00'
    ws_markets.cell(row=10, column=6, value="=SUM(F4:F9)").font = bold_font
    ws_markets.cell(row=10, column=6).number_format = '#,##0.00'
    
    for col in range(1, 7):
        ws_markets.cell(row=10, column=col).border = thin_border
        ws_markets.cell(row=10, column=col).alignment = center_align
        ws_markets.cell(row=10, column=col).fill = yellow_fill
    
    # عرض الأعمدة
    for col in ['A', 'B', 'C', 'D', 'E', 'F']:
        ws_markets.column_dimensions[col].width = 18
    
    # ==========================================
    # Sheet 5: الرسوم البيانية
    # ==========================================
    ws_charts = wb.create_sheet("الرسوم البيانية")
    
    ws_charts.merge_cells('A1:L1')
    ws_charts['A1'].value = "📈 الرسوم البيانية التفاعلية"
    ws_charts['A1'].font = title_font
    ws_charts['A1'].fill = title_fill
    ws_charts['A1'].alignment = center_align
    ws_charts.row_dimensions[1].height = 40
    
    # رسم بياني 1: توزيع الصفقات (Pie Chart)
    pie_data = ws_charts['A3:B5']
    ws_charts['A3'] = "الحالة"
    ws_charts['B3'] = "العدد"
    ws_charts['A4'] = "رابحة"
    ws_charts['B4'] = "=COUNTIF(البيانات!K4:K103,\">0\")"
    ws_charts['A5'] = "خاسرة"
    ws_charts['B5'] = "=COUNTIF(البيانات!K4:K103,\"<0\")"
    
    pie = PieChart()
    pie.title = "توزيع الصفقات (رابحة vs خاسرة)"
    pie.style = 10
    labels = Reference(ws_charts, min_col=1, min_row=4, max_row=5)
    data = Reference(ws_charts, min_col=2, min_row=3, max_row=5)
    pie.add_data(data, titles_from_data=True)
    pie.set_categories(labels)
    pie.width = 15
    pie.height = 10
    ws_charts.add_chart(pie, "D3")
    
    # رسم بياني 2: الأداء حسب السوق (Bar Chart)
    bar = BarChart()
    bar.type = "col"
    bar.title = "نسبة النجاح حسب السوق"
    bar.style = 10
    bar.y_axis.title = "نسبة النجاح %"
    bar.x_axis.title = "السوق"
    
    data_ref = Reference(ws_markets, min_col=5, min_row=3, max_row=9)
    cats_ref = Reference(ws_markets, min_col=1, min_row=4, max_row=9)
    bar.add_data(data_ref, titles_from_data=True)
    bar.set_categories(cats_ref)
    bar.width = 18
    bar.height = 10
    ws_charts.add_chart(bar, "D20")
    
    # رسم بياني 3: فعالية LSTM
    lstm_bar = BarChart()
    lstm_bar.type = "col"
    lstm_bar.title = "فعالية LSTM - نسبة النجاح"
    lstm_bar.style = 10
    lstm_bar.y_axis.title = "نسبة النجاح %"
    
    data_ref = Reference(ws_lstm, min_col=4, min_row=3, max_row=5)
    cats_ref = Reference(ws_lstm, min_col=1, min_row=4, max_row=5)
    lstm_bar.add_data(data_ref, titles_from_data=True)
    lstm_bar.set_categories(cats_ref)
    lstm_bar.width = 15
    lstm_bar.height = 10
    ws_charts.add_chart(lstm_bar, "D37")
    
    # ==========================================
    # Sheet 6: التوصيات الذكية
    # ==========================================
    ws_rec = wb.create_sheet("التوصيات الذكية")
    
    ws_rec.merge_cells('A1:D1')
    ws_rec['A1'].value = "💡 التوصيات الذكية بناءً على الأداء"
    ws_rec['A1'].font = title_font
    ws_rec['A1'].fill = title_fill
    ws_rec['A1'].alignment = center_align
    ws_rec.row_dimensions[1].height = 40
    
    # التوصيات
    recommendations = [
        ('📊 حالة البوت العامة', '=IF(AND(التحليل!B7>=50,التحليل!B13>=1.5),"✅ البوت يعمل بشكل جيد - استمر في الاستراتيجية الحالية","⚠️ البوت يحتاج تحسينات - راجع الاستراتيجية")'),
        ('🧠 فعالية LSTM', '=IF(تحليل_LSTM!D6>10,"✅ LSTM يضيف قيمة كبيرة - استمر في استخدامه","⚠️ LSTM لا يضيف قيمة كافية - فكّر في تعديله")'),
        ('💰 إدارة المخاطر', '=IF(التحليل!B13>=2,"✅ نسبة Risk/Reward ممتازة","⚠️ حسّن نسبة Risk/Reward - زد Take Profit أو قلل Stop Loss")'),
        ('📈 أفضل سوق', '=INDEX(تحليل_الأسواق!A4:A9,MATCH(MAX(تحليل_الأسواق!E4:E9),تحليل_الأسواق!E4:E9,0))&" - نسبة نجاح: "&TEXT(MAX(تحليل_الأسواق!E4:E9),"0.00")&"%"'),
        ('📉 أسوأ سوق', '=INDEX(تحليل_الأسواق!A4:A9,MATCH(MIN(تحليل_الأسواق!E4:E9),تحليل_الأسواق!E4:E9,0))&" - نسبة نجاح: "&TEXT(MIN(تحليل_الأسواق!E4:E9),"0.00")&"%"'),
        ('', ''),
        ('🎯 خطة العمل للأسبوع القادم', ''),
        ('1.', '=IF(التحليل!B7>=60,"استمر بنفس الاستراتيجية - الأداء ممتاز","راقب الصفقات الخاسرة وحلّل أسبابها")'),
        ('2.', '=IF(تحليل_LSTM!D6>10,"زد ثقة LSTM في اتخاذ القرارات","راجع نموذج LSTM وأعد تدريبه ببيانات أحدث")'),
        ('3.', '=IF(التحليل!B13>=2,"حافظ على نفس نسب SL/TP","عدّل SL/TP لتحسين Risk/Reward")'),
        ('4.', 'قلل التداول في السوق الأسوأ أداءً'),
        ('5.', 'زد التركيز على السوق الأفضل أداءً'),
    ]
    
    row = 3
    for label, formula in recommendations:
        if label == '' and formula == '':
            row += 1
            continue
        
        ws_rec.cell(row=row, column=1, value=label).font = bold_font
        ws_rec.cell(row=row, column=1).alignment = left_align
        ws_rec.cell(row=row, column=1).border = thin_border
        ws_rec.cell(row=row, column=1).fill = light_blue_fill
        
        if formula:
            ws_rec.merge_cells(f'B{row}:D{row}')
            value_cell = ws_rec.cell(row=row, column=2, value=formula)
            value_cell.font = Font(name='Calibri', size=11)
            value_cell.alignment = left_align
            value_cell.border = thin_border
        
        row += 1
    
    # عرض الأعمدة
    ws_rec.column_dimensions['A'].width = 30
    ws_rec.column_dimensions['B'].width = 30
    ws_rec.column_dimensions['C'].width = 25
    ws_rec.column_dimensions['D'].width = 25
    
    # ==========================================
    # حفظ الملف
    # ==========================================
    filename = f"قالب_تقييم_الأداء_{datetime.now().strftime('%Y%m%d')}.xlsx"
    wb.save(filename)
    print(f"✅ تم إنشاء القالب: {filename}")
    
    return filename

# ==========================================
# 5. التشغيل الرئيسي
# ==========================================
def main():
    print(f"🚀 بدء إنشاء قالب تقييم الأداء - {datetime.now()}")
    send_telegram("📊 <b>جاري إنشاء قالب تقييم الأداء...</b>")
    
    try:
        filename = create_performance_template()
        
        # إرسال رسالة النجاح
        success_msg = f"""
✅ <b>تم إنشاء قالب تقييم الأداء بنجاح!</b>

📁 <b>اسم الملف:</b> {filename}

📋 <b>يحتوي القالب على 6 أوراق:</b>

1️⃣ <b>البيانات:</b> أدخل صفقاتك هنا
2️⃣ <b>التحليل:</b> حسابات تلقائية
3️⃣ <b>تحليل LSTM:</b> فعالية الذكاء الاصطناعي
4️⃣ <b>تحليل الأسواق:</b> أداء كل سوق
5️⃣ <b>الرسوم البيانية:</b> تصور البيانات
6️⃣ <b>التوصيات الذكية:</b> نصائح تلقائية

⚙️ <b>طريقة الاستخدام:</b>
• افتح الملف في Excel
• اذهب لورقة "البيانات"
• أدخل صفقاتك (التاريخ، الرمز، السعر...)
• كل الحسابات ستُحدّث تلقائياً!

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        send_telegram(success_msg)
        
        # إرسال الملف
        if send_telegram_document(filename):
            send_telegram("📎 <b>تم إرسال ملف Excel بنجاح!</b>")
        else:
            send_telegram("⚠️ <b>فشل إرسال الملف. يمكنك تحميله من GitHub.</b>")
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        send_telegram(f"❌ <b>فشل إنشاء القالب:</b>\n{str(e)[:200]}")

if __name__ == "__main__":
    main()
