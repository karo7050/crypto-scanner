"""
ماژول تولید گزارش Excel
Report Generator Module
- شیت Long Signals (10 پیشنهاد لانگ)
- شیت Short Signals (10 پیشنهاد شورت)
- شیت Raw Data (داده‌های خام)
- شیت Summary Stats
"""
import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows
from datetime import datetime
from typing import Dict, List
import os
import config


class ReportGenerator:
    """تولید گزارش Excel حرفه‌ای"""

    # رنگ‌ها
    GREEN_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    RED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    YELLOW_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    SUBHEADER_FILL = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
    HEADER_FONT = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    TITLE_FONT = Font(name="Arial", size=14, bold=True, color="2F5496")
    BODY_FONT = Font(name="Arial", size=10)
    BOLD_FONT = Font(name="Arial", size=10, bold=True)
    CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
    LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
    BORDER = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC')
    )

    @classmethod
    def generate(cls, signals: Dict, all_scored: list, scan_summary: Dict) -> str:
        """تولید فایل Excel کامل"""
        timestamp = config.tehran_now().strftime('%Y%m%d_%H%M%S')
        filename = config.OUTPUT_FILE.format(timestamp=timestamp)
        filepath = os.path.join(config.OUTPUT_DIR, filename)

        wb = Workbook()

        # حذف شیت پیش‌فرض
        wb.remove(wb.active)

        # ساخت شیت‌ها
        cls._create_summary_sheet(wb, scan_summary)
        cls._create_signals_sheet(wb, signals.get('long', []), 'Long Signals', is_long=True)
        cls._create_signals_sheet(wb, signals.get('short', []), 'Short Signals', is_long=False)
        cls._create_all_coins_sheet(wb, all_scored)
        cls._create_methodology_sheet(wb)

        wb.save(filepath)
        return filepath

    # ----------------- شیت خلاصه -----------------
    @classmethod
    def _create_summary_sheet(cls, wb, summary):
        ws = wb.create_sheet("Summary", 0)

        # عنوان
        ws['A1'] = "گزارش اسکنر کریپتو - خلاصه"
        ws['A1'].font = cls.TITLE_FONT
        ws.merge_cells('A1:F1')
        ws['A1'].alignment = cls.CENTER

        ws['A2'] = f"زمان تولید: {config.tehran_now().strftime('%Y-%m-%d %H:%M:%S')}"
        ws['A2'].font = cls.BODY_FONT
        ws.merge_cells('A2:F2')

        # اطلاعات خلاصه
        rows = [
            ('', ''),
            ('معیار', 'مقدار'),
            ('حداقل مارکت کپ', f"${config.MIN_MARKET_CAP_USD:,.0f}"),
            ('تایم فریم‌های تحلیل شده', ' → '.join(config.TIMEFRAMES)),
            ('تعداد کوین‌های اسکن شده', summary.get('total_scanned', 0)),
            ('تعداد کوین‌های دارای داده کامل', summary.get('successful', 0)),
            ('پیشنهادهای لانگ', summary.get('long_count', 0)),
            ('پیشنهادهای شورت', summary.get('short_count', 0)),
            ('مدت زمان اسکن (ثانیه)', round(summary.get('duration_sec', 0), 1)),
            ('صرافی', config.EXCHANGE_ID.title()),
            ('', ''),
            ('وزن‌های امتیازدهی', ''),
            ('هماهنگی روند چند تایم فریم', f"{config.SCORE_WEIGHTS['trend_alignment']}%"),
            ('مومنتوم (RSI/MACD)', f"{config.SCORE_WEIGHTS['momentum']}%"),
            ('نقدینگی و جریان پول', f"{config.SCORE_WEIGHTS['liquidity']}%"),
            ('حجم معاملات', f"{config.SCORE_WEIGHTS['volume']}%"),
            ('ساختار قیمت + Order Book', f"{config.SCORE_WEIGHTS['structure']}%"),
        ]

        for row_idx, (label, value) in enumerate(rows, start=4):
            ws.cell(row=row_idx, column=1, value=label).font = cls.BOLD_FONT
            ws.cell(row=row_idx, column=1).alignment = cls.LEFT
            ws.cell(row=row_idx, column=2, value=value).font = cls.BODY_FONT
            ws.cell(row=row_idx, column=2).alignment = cls.LEFT
            if label == 'معیار':
                ws.cell(row=row_idx, column=1).fill = cls.SUBHEADER_FILL
                ws.cell(row=row_idx, column=2).fill = cls.SUBHEADER_FILL

        ws.column_dimensions['A'].width = 35
        ws.column_dimensions['B'].width = 45

    # ----------------- شیت سیگنال‌ها -----------------
    @classmethod
    def _create_signals_sheet(cls, wb, signals, sheet_name, is_long=True):
        ws = wb.create_sheet(sheet_name)

        # عنوان
        title = f"پیشنهادهای {'لانگ (LONG)' if is_long else 'شورت (SHORT)'} - 10 ارز برتر"
        ws['A1'] = title
        ws['A1'].font = cls.TITLE_FONT
        ws.merge_cells('A1:J1')
        ws['A1'].alignment = cls.CENTER

        # هدر ستون‌ها
        headers = [
            'رتبه', 'سیمبل', 'نام', 'مارکت کپ (M$)', 'قیمت فعلی',
            'امتیاز', 'نقطه ورود', 'استاپ لاس', 'هدف 2 (RR 1:2)',
            'Risk/Reward', 'استاپ (%)', 'استراتژی ورود',
            'روند 1d', 'روند 4h', 'روند 1h', 'روند 15m',
            'ساختار', 'فاز نقدینگی', 'فشار Order Book',
            'دلایل انتخاب'
        ]

        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=3, column=col_idx, value=header)
            cell.font = cls.HEADER_FONT
            cell.fill = cls.HEADER_FILL
            cell.alignment = cls.CENTER
            cell.border = cls.BORDER

        # داده‌ها
        for rank, signal in enumerate(signals, start=1):
            row_idx = 3 + rank
            coin = signal.get('coin', {})
            setup = signal.get('setup', {})
            trend = signal.get('trend_alignment', {})
            structure = signal.get('structure', {})
            ob = signal.get('order_book', {})
            reasons = signal.get('long_reasons' if is_long else 'short_reasons', [])
            score = signal.get('long_score' if is_long else 'short_score', 0)

            row_data = [
                rank,
                coin.get('base', ''),
                coin.get('name', ''),
                round(coin.get('market_cap', 0) / 1_000_000, 1),
                setup.get('current_price', 0),
                score,
                setup.get('entry_price', 0),
                setup.get('stop_loss', 0),
                setup.get('target_2', 0),
                setup.get('risk_reward', 0),
                f"{setup.get('stop_pct', 0)}%",
                setup.get('entry_strategy', ''),
                trend.get('trend_dirs', {}).get('1d', '-'),
                trend.get('trend_dirs', {}).get('4h', '-'),
                trend.get('trend_dirs', {}).get('1h', '-'),
                trend.get('trend_dirs', {}).get('15m', '-'),
                structure.get('overall_structure', '-'),
                signal.get('state_1h', {}).get('trend_dir', '-') if isinstance(signal.get('state_1h'), dict) else '-',
                ob.get('pressure', '-') if ob else '-',
                ' | '.join(reasons),
            ]

            for col_idx, value in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = cls.BODY_FONT
                cell.alignment = cls.CENTER if col_idx <= 18 else cls.LEFT
                cell.border = cls.BORDER
                # رنگ‌بندی ردیف
                if is_long:
                    cell.fill = cls.GREEN_FILL if rank <= 3 else cls.YELLOW_FILL if rank <= 6 else PatternFill()
                else:
                    cell.fill = cls.RED_FILL if rank <= 3 else cls.YELLOW_FILL if rank <= 6 else PatternFill()

        # عرض ستون‌ها
        col_widths = [6, 12, 18, 14, 12, 10, 14, 14, 14, 12, 10, 30, 12, 12, 12, 12, 25, 15, 18, 60]
        for i, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width

        # فریز هدر
        ws.freeze_panes = 'A4'

    # ----------------- شیت همه کوین‌ها -----------------
    @classmethod
    def _create_all_coins_sheet(cls, wb, all_scored):
        ws = wb.create_sheet("All Coins Analysis")

        ws['A1'] = "تحلیل همه کوین‌های اسکن شده"
        ws['A1'].font = cls.TITLE_FONT
        ws.merge_cells('A1:M1')

        headers = [
            'سیمبل', 'نام', 'مارکت کپ (M$)', 'قیمت فعلی',
            'امتیاز لانگ', 'امتیاز شورت', 'روند کلی',
            'ساختار قیمت', 'تایم فریم‌های هماهنگ',
            'فشار Order Book', 'RSI 1h', 'RSI 15m', 'ADX'
        ]

        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=3, column=col_idx, value=header)
            cell.font = cls.HEADER_FONT
            cell.fill = cls.HEADER_FILL
            cell.alignment = cls.CENTER
            cell.border = cls.BORDER

        for row_idx, score in enumerate(all_scored, start=4):
            coin = score.get('coin', {})
            trend = score.get('trend_alignment', {})
            structure = score.get('structure', {})
            ob = score.get('order_book', {})
            state_1h = score.get('state_1h', {})
            state_15m = score.get('state_15m', {})

            row_data = [
                coin.get('base', ''),
                coin.get('name', ''),
                round(coin.get('market_cap', 0) / 1_000_000, 1),
                coin.get('current_price', 0),
                score.get('long_score', 0),
                score.get('short_score', 0),
                trend.get('overall_bias', '-'),
                structure.get('overall_structure', '-'),
                f"1d:{trend.get('trend_dirs', {}).get('1d', '-')} / 4h:{trend.get('trend_dirs', {}).get('4h', '-')} / 1h:{trend.get('trend_dirs', {}).get('1h', '-')} / 15m:{trend.get('trend_dirs', {}).get('15m', '-')}",
                ob.get('pressure', '-') if ob else '-',
                round(state_1h.get('rsi', 0), 1) if isinstance(state_1h, dict) else '-',
                round(state_15m.get('rsi', 0), 1) if isinstance(state_15m, dict) else '-',
                round(state_1h.get('adx', 0), 1) if isinstance(state_1h, dict) else '-',
            ]

            for col_idx, value in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = cls.BODY_FONT
                cell.alignment = cls.CENTER if col_idx <= 11 else cls.LEFT
                cell.border = cls.BORDER
                # برجسته کردن برترین‌ها
                if col_idx == 5 and score.get('long_score', 0) > 50:
                    cell.fill = cls.GREEN_FILL
                if col_idx == 6 and score.get('short_score', 0) > 50:
                    cell.fill = cls.RED_FILL

        col_widths = [12, 18, 14, 12, 12, 12, 22, 25, 35, 20, 10, 10, 10]
        for i, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width

        ws.freeze_panes = 'A4'
        ws.auto_filter.ref = f"A3:M{3 + len(all_scored)}"

    # ----------------- شیت متدولوژی -----------------
    @classmethod
    def _create_methodology_sheet(cls, wb):
        ws = wb.create_sheet("Methodology")

        ws['A1'] = "متدولوژی و راهنمای استفاده"
        ws['A1'].font = cls.TITLE_FONT
        ws.merge_cells('A1:E1')

        sections = [
            ('', ''),
            ('۱. مراحل تحلیل', ''),
            ('گام 1', 'دریافت لیست کوین‌های با مارکت کپ > 100M دلار از CoinGecko'),
            ('گام 2', 'دریافت داده OHLCV برای تایم فریم‌های 1d, 4h, 1h, 15m از Binance'),
            ('گام 3', 'محاسبه اندیکاتورها: RSI, EMA20/50/200, MACD, ATR, Bollinger Bands, ADX, Stochastic'),
            ('گام 4', 'تحلیل نقدینگی: MFI, OBV, CMF, ADL, Force Index, تشخیص انباشت/توزیع'),
            ('گام 5', 'تحلیل Order Book: فشار خرید/فروش، دیوارها، Spread'),
            ('گام 6', 'تحلیل Top-Down: 1d → 4h → 1h → 15m (نقطه ورود)'),
            ('گام 7', 'امتیازدهی جامع با 5 فاکتور: روند، مومنتوم، نقدینگی، حجم، ساختار'),
            ('گام 8', 'محاسبه نقطه ورود، استاپ لاس (ATR + Support/Resistance) و هدف سود (RR 1:2/1:3)'),
            ('گام 9', 'انتخاب 10 لانگ و 10 شورت برتر + تولید دلایل'),
            ('', ''),
            ('۲. امتیازدهی', ''),
            ('هماهنگی روند (30%)', 'بررسی هماهنگی روند در همه تایم فریم‌ها. تایم فریم بالاتر وزن بیشتری دارد.'),
            ('مومنتوم (20%)', 'RSI, MACD, تقاطع EMA. در محدوده سالم (نه اشباع) امتیاز بالاتر.'),
            ('نقدینگی (20%)', 'جریان پول (CMF, OBV, MFI), فاز انباشت/توزیع، تشخیص ورود/خروج پول هوشمند.'),
            ('حجم (15%)', 'نسبت حجم فعلی به میانگین 20 روزه. حجم بالا تأییدکننده حرکت است.'),
            ('ساختار (15%)', 'Order Book pressure، دیوارهای خرید/فروش، نزدیکی به حمایت/مقاومت.'),
            ('', ''),
            ('۳. نقطه ورود و استاپ لاس', ''),
            ('استراتژی ورود', 'سه سناریو: 1) ورود در پولبک به حمایت 2) ورود بعد از شکست مقاومت 3) ورود در قیمت فعلی (با تأیید روند)'),
            ('استاپ لاس', 'حداکثر سطح زیر قیمت ورود از بین: ATR-based (1.5x ATR 1h)، سطح حمایت، دیوار خرید Order Book'),
            ('هدف سود', 'Target 1: RR 1:1.5 / Target 2: RR 1:2 / Target 3: RR 1:3'),
            ('Risk/Reward', 'حداقل RR قابل قبول: 1:2 (برای Target 2)'),
            ('', ''),
            ('۴. تفسیر خروجی', ''),
            ('رنگ سبز', 'امتیاز بالا (Top 3)'),
            ('رنگ زرد', 'امتیاز متوسط (Top 4-6)'),
            ('بدون رنگ', 'امتیاز پایین‌تر (Top 7-10)'),
            ('', ''),
            ('۵. هشدارها', ''),
            ('این گزارش یک ابزار تحلیلی است', 'نه توصیه سرمایه‌گذاری. همیشه مدیریت ریسک شخصی اعمال کنید.'),
            ('سیگنال‌ها ناپایدارند', 'بازار کریپتو نوسان بالایی دارد. در صورت تغییر شرایط، سیگنال‌ها به‌روز می‌شوند.'),
            ('برای استفاده بهینه', 'سیگنال‌ها را هر 1-4 ساعت یک‌بار به‌روزرسانی کنید.'),
            ('تمرکز روی امتیاز بالاتر', 'پیشنهاد می‌شود اولویت با ارزهای رتبه 1-3 باشد (سبز).'),
        ]

        for row_idx, (label, value) in enumerate(sections, start=3):
            ws.cell(row=row_idx, column=1, value=label).font = cls.BOLD_FONT
            ws.cell(row=row_idx, column=1).alignment = cls.LEFT
            ws.cell(row=row_idx, column=2, value=value).font = cls.BODY_FONT
            ws.cell(row=row_idx, column=2).alignment = cls.LEFT
            if label and not value:
                ws.cell(row=row_idx, column=1).fill = cls.SUBHEADER_FILL

        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 80
