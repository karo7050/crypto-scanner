"""
ماژول تولید گزارش PDF
PDF Report Generator for Crypto Scanner
- استفاده از فونت Vazirmatn برای فارسی
- arabic_reshaper + bidi برای رندر صحیح RTL
- گزارش حرفه‌ای با جداول و دلایل کامل
"""
import os
import sys
from datetime import datetime
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import arabic_reshaper
from bidi.algorithm import get_display

import config

# ============ ثبت فونت‌ها ============
# مسیر فونت: از env یا مسیر پیش‌فرض
FONT_DIR = os.environ.get('FONT_DIR', '/home/z/my-project/fonts')
if not os.path.exists(FONT_DIR):
    # مسیرهای جایگزین
    for alt in [os.path.expanduser('~/fonts'), '/home/runner/fonts', '/usr/share/fonts']:
        if os.path.exists(alt):
            FONT_DIR = alt
            break

# ثبت فونت‌ها (با fallback)
_font_regular = os.path.join(FONT_DIR, 'Vazirmatn-Regular.ttf')
_font_bold = os.path.join(FONT_DIR, 'Vazirmatn-Bold.ttf')
_font_medium = os.path.join(FONT_DIR, 'Vazirmatn-Medium.ttf')

# اگر فونت Vazirmatn موجود نیست، از SimHei استفاده کن
if not os.path.exists(_font_regular):
    _font_regular = os.path.join(FONT_DIR, 'simhei.ttf')
    _font_bold = _font_regular
    _font_medium = _font_regular

try:
    pdfmetrics.registerFont(TTFont('Vazir', _font_regular))
    pdfmetrics.registerFont(TTFont('Vazir-Bold', _font_bold if os.path.exists(_font_bold) else _font_regular))
    pdfmetrics.registerFont(TTFont('Vazir-Medium', _font_medium if os.path.exists(_font_medium) else _font_regular))
except Exception as e:
    # fallback: استفاده از فونت پیش‌فرض ReportLab
    import logging
    logging.warning(f"ثبت فونت ناموفق: {e}. استفاده از فونت پیش‌فرض.")


def fa(text) -> str:
    """رندر صحیح متن فارسی برای PDF (RTL + reshaping)"""
    if text is None:
        return ''
    text = str(text)
    # اگر متن انگلیسی/عددی خالی است، همان را برگردان
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


# ============ استایل‌ها ============
def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='FaTitle',
        fontName='Vazir-Bold',
        fontSize=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1F3864'),
        spaceAfter=10,
        leading=28,
    ))

    styles.add(ParagraphStyle(
        name='FaSubtitle',
        fontName='Vazir',
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#666666'),
        spaceAfter=20,
        leading=16,
    ))

    styles.add(ParagraphStyle(
        name='FaHeading',
        fontName='Vazir-Bold',
        fontSize=16,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#1F3864'),
        spaceBefore=15,
        spaceAfter=10,
        leading=20,
    ))

    styles.add(ParagraphStyle(
        name='FaSubHeading',
        fontName='Vazir-Bold',
        fontSize=13,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#2F5496'),
        spaceBefore=10,
        spaceAfter=8,
        leading=17,
    ))

    styles.add(ParagraphStyle(
        name='FaBody',
        fontName='Vazir',
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
        leading=14,
    ))

    styles.add(ParagraphStyle(
        name='FaCell',
        fontName='Vazir',
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#333333'),
        leading=12,
    ))

    styles.add(ParagraphStyle(
        name='FaCellRight',
        fontName='Vazir',
        fontSize=9,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#333333'),
        leading=12,
    ))

    styles.add(ParagraphStyle(
        name='FaReason',
        fontName='Vazir',
        fontSize=9,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#444444'),
        leading=13,
        rightIndent=10,
    ))

    styles.add(ParagraphStyle(
        name='FaHeader',
        fontName='Vazir-Bold',
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.white,
        leading=12,
    ))

    return styles


# ============ هدر و فوتر ============
def header_footer(canvas, doc):
    """هدر و فوتر برای هر صفحه"""
    canvas.saveState()
    # هدر
    canvas.setFont('Vazir', 8)
    canvas.setFillColor(colors.HexColor('#888888'))
    canvas.drawString(2 * cm, A4[1] - 1.2 * cm, fa('اسکنر کریپتو - گزارش سیگنال‌های لانگ و شورت'))
    canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.2 * cm, config.tehran_now().strftime('%Y-%m-%d %H:%M'))
    # خط زیر هدر
    canvas.setStrokeColor(colors.HexColor('#CCCCCC'))
    canvas.line(2 * cm, A4[1] - 1.4 * cm, A4[0] - 2 * cm, A4[1] - 1.4 * cm)
    # فوتر - شماره صفحه
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, fa(f'صفحه {doc.page}'))
    canvas.restoreState()


# ============ تولید گزارش ============
def generate_pdf(signals: Dict, all_scored: list, scan_summary: Dict) -> str:
    """تولید فایل PDF کامل"""
    timestamp = config.tehran_now().strftime('%Y%m%d_%H%M%S')
    filename = f'crypto_signals_{timestamp}.pdf'
    filepath = os.path.join(config.OUTPUT_DIR, filename)

    # سند با اندازه A4
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title='Crypto Scanner Report',
        author='Crypto Scanner'
    )

    styles = get_styles()
    story = []

    # ============ صفحه عنوان ============
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph(fa('گزارش اسکنر کریپتو'), styles['FaTitle']))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(fa('تحلیل چند تایم فریم + نقدینگی + Order Book'), styles['FaSubtitle']))
    story.append(Spacer(1, 1 * cm))

    # جدول اطلاعات خلاصه
    summary_data = [
        [fa('تاریخ تولید'), config.tehran_now().strftime('%Y-%m-%d %H:%M:%S')],
        [fa('حداقل مارکت کپ'), f'${config.MIN_MARKET_CAP_USD:,.0f}'],
        [fa('تایم فریم‌های تحلیل'), ' → '.join(config.TIMEFRAMES)],
        [fa('تعداد کوین‌های اسکن شده'), str(scan_summary.get('total_scanned', 0))],
        [fa('تحلیل‌های موفق'), str(scan_summary.get('successful', 0))],
        [fa('پیشنهادهای لانگ'), str(scan_summary.get('long_count', 0))],
        [fa('پیشنهادهای شورت'), str(scan_summary.get('short_count', 0))],
        [fa('مدت زمان اسکن'), f"{round(scan_summary.get('duration_sec', 0), 1)} ثانیه"],
        [fa('صرافی'), config.EXCHANGE_ID.title()],
    ]

    summary_table = Table(summary_data, colWidths=[6 * cm, 10 * cm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#D6E4F0')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1F3864')),
        ('FONTNAME', (0, 0), (0, -1), 'Vazir-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)

    story.append(PageBreak())

    # ============ بخش سیگنال‌های لانگ ============
    story.append(Paragraph(fa('سیگنال‌های لانگ (LONG)'), styles['FaHeading']))
    story.append(Paragraph(
        fa('10 ارز برتر برای پوزیشن لانگ بر اساس تحلیل چند تایم فریم، نقدینگی و Order Book'),
        styles['FaBody']
    ))
    story.append(Spacer(1, 0.5 * cm))

    long_signals = signals.get('long', [])
    _build_signals_table(story, long_signals, styles, is_long=True)

    # ============ صفحه جدید برای شورت ============
    story.append(PageBreak())
    story.append(Paragraph(fa('سیگنال‌های شورت (SHORT)'), styles['FaHeading']))
    story.append(Paragraph(
        fa('10 ارز برتر برای پوزیشن شورت بر اساس تحلیل چند تایم فریم، نقدینگی و Order Book'),
        styles['FaBody']
    ))
    story.append(Spacer(1, 0.5 * cm))

    short_signals = signals.get('short', [])
    _build_signals_table(story, short_signals, styles, is_long=False)

    # ============ بخش متدولوژی ============
    story.append(PageBreak())
    story.append(Paragraph(fa('متدولوژی و راهنما'), styles['FaHeading']))

    methodology_sections = [
        ('مراحل تحلیل', [
            'دریافت لیست کوین‌های با مارکت کپ بالای 100 میلیون دلار از CoinGecko',
            'دریافت داده OHLCV برای تایم فریم‌های 1d, 4h, 1h, 15m از صرافی',
            'محاسبه اندیکاتورها: RSI, EMA20/50/200, MACD, ATR, Bollinger Bands, ADX, Stochastic',
            'تحلیل نقدینگی: MFI, OBV, CMF, ADL, Force Index، تشخیص انباشت/توزیع',
            'تحلیل Order Book: فشار خرید/فروش، دیوارها، Spread',
            'تحلیل Top-Down: 1d → 4h → 1h → 15m (نقطه ورود)',
            'امتیازدهی جامع با 5 فاکتور و انتخاب 10 لانگ و 10 شورت برتر',
        ]),
        ('سیستم امتیازدهی', [
            'هماهنگی روند چند تایم فریم (30%): تایم فریم بالاتر وزن بیشتر',
            'مومنتوم (20%): RSI, MACD, تقاطع EMA در محدوده سالم',
            'نقدینگی و جریان پول (20%): CMF, OBV, فاز انباشت/توزیع',
            'حجم معاملات (15%): نسبت حجم فعلی به میانگین 20 روزه',
            'ساختار + Order Book (15%): فشار خرید/فروش، دیوارهای نقدینگی',
        ]),
        ('نقطه ورود و استاپ لاس', [
            'سه سناریو ورود: پولبک به حمایت، شکست مقاومت، قیمت فعلی',
            'استاپ لاس: ترکیب ATR (1.5x)، سطح حمایت/مقاومت، دیوار Order Book',
            'اهداف سود: Target 1 (RR 1:1.5)، Target 2 (RR 1:2)، Target 3 (RR 1:3)',
            'حداقل Risk/Reward قابل قبول: 1:2',
        ]),
        ('تفسیر رنگ‌ها', [
            'رنگ سبز: امتیاز بالا (Top 3)',
            'رنگ زرد: امتیاز متوسط (Top 4-6)',
            'بدون رنگ: امتیاز پایین‌تر (Top 7-10)',
        ]),
        ('هشدارها', [
            'این گزارش یک ابزار تحلیلی است، نه توصیه سرمایه‌گذاری',
            'همیشه مدیریت ریسک شخصی اعمال کنید',
            'سیگنال‌ها را هر 1-4 ساعت به‌روزرسانی کنید',
            'بازار کریپتو نوسان بالایی دارد',
        ]),
    ]

    for heading, items in methodology_sections:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(fa(heading), styles['FaSubHeading']))
        for item in items:
            story.append(Paragraph(f'• {fa(item)}', styles['FaReason']))

    # تولید PDF
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return filepath


def _build_signals_table(story, signals, styles, is_long=True):
    """ساخت جدول سیگنال‌ها با جزئیات کامل"""
    if not signals:
        story.append(Paragraph(fa('سیگنالی یافت نشد.'), styles['FaBody']))
        return

    # هدر جدول خلاصه
    header_color = colors.HexColor('#2E7D32') if is_long else colors.HexColor('#C62828')
    light_color = colors.HexColor('#E8F5E9') if is_long else colors.HexColor('#FFEBEE')

    headers = ['#', 'سیمبل', 'امتیاز', 'قیمت فعلی', 'نقطه ورود', 'استاپ لاس',
               'هدف (RR 1:2)', 'استاپ %', 'RR']

    data = [[Paragraph(fa(h), styles['FaHeader']) for h in headers]]

    for i, signal in enumerate(signals[:10], 1):
        coin = signal.get('coin', {})
        setup = signal.get('setup', {})
        score = signal.get('long_score' if is_long else 'short_score', 0)

        row = [
            str(i),
            coin.get('base', ''),
            f'{score:.1f}',
            _fmt_price(setup.get('current_price', 0)),
            _fmt_price(setup.get('entry_price', 0)),
            _fmt_price(setup.get('stop_loss', 0)),
            _fmt_price(setup.get('target_2', 0)),
            f"{setup.get('stop_pct', 0)}%",
            f"{setup.get('risk_reward', 0)}",
        ]
        data.append([Paragraph(fa(c), styles['FaCell']) for c in row])

    # رنگ‌بندی ردیف‌ها
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Vazir-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]

    # رنگ ردیف‌های برتر
    for i in range(1, min(4, len(data))):
        table_style.append(('BACKGROUND', (0, i), (-1, i), light_color))

    table = Table(data, colWidths=[1 * cm, 2 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 1.5 * cm, 1 * cm])
    table.setStyle(TableStyle(table_style))
    story.append(table)

    # ============ جزئیات دلایل هر سیگنال ============
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(fa('دلایل انتخاب و تحلیل تفصیلی'), styles['FaSubHeading']))
    story.append(Spacer(1, 0.2 * cm))

    for i, signal in enumerate(signals[:10], 1):
        coin = signal.get('coin', {})
        setup = signal.get('setup', {})
        trend = signal.get('trend_alignment', {})
        structure = signal.get('structure', {})
        ob = signal.get('order_book', {})
        reasons = signal.get('long_reasons' if is_long else 'short_reasons', [])
        score = signal.get('long_score' if is_long else 'short_score', 0)

        # عنوان ارز
        story.append(Paragraph(
            fa(f'{i}. {coin.get("base", "")} - {coin.get("name", "")} | امتیاز: {score:.1f} | مارکت کپ: ${coin.get("market_cap", 0)/1e6:.0f}M'),
            styles['FaSubHeading']
        ))

        # اطلاعات نقطه ورود
        entry_info = [
            [fa('استراتژی ورود'), fa(setup.get('entry_strategy', '-'))],
            [fa('قیمت فعلی'), _fmt_price(setup.get('current_price', 0))],
            [fa('نقطه ورود'), _fmt_price(setup.get('entry_price', 0))],
            [fa('استاپ لاس'), _fmt_price(setup.get('stop_loss', 0))],
            [fa('درصد استاپ'), f"{setup.get('stop_pct', 0)}%"],
            [fa('هدف 1 (RR 1:1.5)'), _fmt_price(setup.get('target_1', 0))],
            [fa('هدف 2 (RR 1:2)'), _fmt_price(setup.get('target_2', 0))],
            [fa('هدف 3 (RR 1:3)'), _fmt_price(setup.get('target_3', 0))],
            [fa('Risk/Reward'), f"{setup.get('risk_reward', 0)}"],
            [fa('حمایت نزدیک'), _fmt_price(setup.get('nearest_support', 0))],
            [fa('مقاومت نزدیک'), _fmt_price(setup.get('nearest_resistance', 0))],
        ]

        entry_table = Table(entry_info, colWidths=[4.5 * cm, 11.5 * cm])
        entry_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
            ('FONTNAME', (0, 0), (0, -1), 'Vazir-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#DDDDDD')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(entry_table)
        story.append(Spacer(1, 0.2 * cm))

        # روند چند تایم فریم
        trend_dirs = trend.get('trend_dirs', {})
        story.append(Paragraph(
            fa(f'روند چند تایم فریم: 1d: {trend_dirs.get("1d", "-")} | 4h: {trend_dirs.get("4h", "-")} | 1h: {trend_dirs.get("1h", "-")} | 15m: {trend_dirs.get("15m", "-")}'),
            styles['FaReason']
        ))
        story.append(Paragraph(
            fa(f'جهت کلی: {trend.get("overall_bias", "-")} (امتیاز هماهنگی: {trend.get("alignment_pct", 0):.0f}%)'),
            styles['FaReason']
        ))
        story.append(Paragraph(
            fa(f'ساختار قیمت: {structure.get("overall_structure", "-")}'),
            styles['FaReason']
        ))
        if ob:
            story.append(Paragraph(
                fa(f'فشار Order Book: {ob.get("pressure", "-")} | عدم تعادل: {ob.get("imbalance", 0):.2f}'),
                styles['FaReason']
            ))
        story.append(Spacer(1, 0.15 * cm))

        # دلایل انتخاب
        story.append(Paragraph(fa('دلایل انتخاب:'), styles['FaBody']))
        for reason in reasons:
            story.append(Paragraph(f'• {fa(reason)}', styles['FaReason']))

        story.append(Spacer(1, 0.4 * cm))


def _fmt_price(price) -> str:
    """فرمت‌بندی قیمت بر اساس مقدار"""
    if price is None or price == 0:
        return '-'
    if price >= 1000:
        return f'{price:,.2f}'
    elif price >= 1:
        return f'{price:.4f}'
    elif price >= 0.01:
        return f'{price:.5f}'
    else:
        return f'{price:.8f}'
