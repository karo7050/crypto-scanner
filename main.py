"""
اسکنر کریپتو - فایل اصلی
Crypto Scanner - Main Orchestrator
- دریافت لیست کوین‌های با مارکت کپ > 100M
- تحلیل چند تایم فریم + تحلیل نقدینگی + Order Book
- انتخاب 10 لانگ و 10 شورت برتر
- خروجی Excel با دلایل کامل انتخاب

استفاده:
    cd /home/z/my-project/download/crypto_scanner
    python3 main.py

متغیرهای محیطی (اختیاری):
    BINANCE_API_KEY - کلید API بایننس (دسترسی Order Book خصوصی)
    BINANCE_API_SECRET - رمز API بایننس
"""
import sys
import os
import time
import copy
import logging
from datetime import datetime

# تنظیم منطقه زمانی تهران برای همه خروجی‌ها
os.environ['TZ'] = 'Asia/Tehran'
try:
    time.tzset()
except AttributeError:
    pass

# اضافه کردن مسیر پروژه
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data_fetcher import DataFetcher
from indicators import Indicators
from liquidity import LiquidityAnalyzer
from multi_tf import MultiTimeframeAnalyzer
from signal_engine import SignalEngine
from entry_exit import EntryExitCalculator
from report import ReportGenerator
from pdf_report import generate_pdf

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(config.OUTPUT_DIR, f'scanner_{config.tehran_now().strftime("%Y%m%d_%H%M%S")}.log'),
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("اسکنر کریپتو - تحلیل چند تایم فریم + نقدینگی + Order Book")
    print("=" * 70)
    print(f"زمان شروع: {config.tehran_now().strftime('%Y-%m-%d %H:%M:%S')} (تهران)")
    print(f"حداقل مارکت کپ: ${config.MIN_MARKET_CAP_USD:,.0f}")
    print(f"تایم فریم‌ها: {' → '.join(config.TIMEFRAMES)}")
    print(f"خروجی: 10 لانگ + 10 شورت")
    print("=" * 70)

    start_time = time.time()

    # ============ راه‌اندازی ============
    fetcher = DataFetcher()

    # ============ دریافت لیست کوین‌ها ============
    logger.info("گام 1/7: دریافت لیست کوین‌های با مارکت کپ بالا...")
    coins = fetcher.fetch_top_market_cap_coins()
    if not coins:
        logger.error("هیچ کوینی یافت نشد. بررسی اتصال اینترنت.")
        return

    logger.info(f"تعداد کوین‌های برای اسکن: {len(coins)}")

    # ============ تحلیل هر کوین ============
    logger.info("گام 2/7: دریافت داده OHLCV چند تایم فریم...")
    logger.info("گام 3/7: محاسبه اندیکاتورها و تحلیل نقدینگی...")
    logger.info("گام 4/7: تحلیل Order Book...")
    logger.info("گام 5/7: تحلیل Top-Down و امتیازدهی...")

    all_scored = []
    successful = 0

    for i, coin in enumerate(coins, start=1):
        symbol = coin['symbol']
        base = coin['base']

        try:
            print(f"  [{i}/{len(coins)}] تحلیل {base}...", end='', flush=True)

            # دریافت داده همه تایم فریم‌ها
            timeframes_data = fetcher.fetch_all_timeframes(symbol)
            if len(timeframes_data) < 3:
                print(" ⚠ داده ناکافی - رد شد")
                continue

            # تحلیل چند تایم فریم
            analysis = MultiTimeframeAnalyzer.analyze_all(timeframes_data)

            # دریافت و تحلیل Order Book
            order_book = fetcher.fetch_order_book(symbol)
            ob_analysis = LiquidityAnalyzer.analyze_order_book(order_book) if order_book else None

            # امتیازدهی
            score = SignalEngine.score_coin(coin, analysis, ob_analysis)

            # ذخیره analysis برای استفاده در محاسبه setup
            score['_analysis'] = analysis
            score['_ob_analysis'] = ob_analysis

            # محاسبه نقطه ورود و استاپ لاس (موقت - بر اساس امتیاز بالاتر)
            if score['long_score'] >= score['short_score']:
                score['setup'] = EntryExitCalculator.calculate_long_setup(analysis, ob_analysis)
            else:
                score['setup'] = EntryExitCalculator.calculate_short_setup(analysis, ob_analysis)

            all_scored.append(score)
            successful += 1
            print(f" ✓ Long:{score['long_score']} Short:{score['short_score']}")

            # مکث کوتاه برای احترام به Rate Limit
            time.sleep(0.3)

        except Exception as e:
            logger.warning(f"خطا در تحلیل {symbol}: {e}")
            continue

    if not all_scored:
        logger.error("تحلیلی انجام نشد. خروج.")
        return

    # ============ انتخاب نهایی ============
    logger.info("گام 6/7: انتخاب 10 لانگ و 10 شورت برتر...")
    top_signals = SignalEngine.select_top_signals(all_scored)

    # ایجاد کپی جداگانه برای لیست لانگ و شورت
    # تا تغییر setup در یک لیست، لیست دیگر را تحت تاثیر قرار ندهد
    long_list = [copy.deepcopy(c) for c in top_signals['long']]
    short_list = [copy.deepcopy(c) for c in top_signals['short']]

    # اطمینان از اینکه هر کوین در لیست لانگ، setup لانگ دارد
    # و هر کوین در لیست شورت، setup شورت دارد
    def ensure_long_setup(coin_score):
        """استفاده از داده ذخیره شده برای محاسبه setup لانگ"""
        if not coin_score.get('setup') or coin_score['setup'].get('direction') != 'LONG':
            analysis = coin_score.get('_analysis')
            ob_a = coin_score.get('_ob_analysis')
            if analysis:
                try:
                    coin_score['setup'] = EntryExitCalculator.calculate_long_setup(analysis, ob_a)
                except Exception as e:
                    logger.warning(f"خطا در محاسبه setup لانگ برای {coin_score['coin']['symbol']}: {e}")

    def ensure_short_setup(coin_score):
        """استفاده از داده ذخیره شده برای محاسبه setup شورت"""
        if not coin_score.get('setup') or coin_score['setup'].get('direction') != 'SHORT':
            analysis = coin_score.get('_analysis')
            ob_a = coin_score.get('_ob_analysis')
            if analysis:
                try:
                    coin_score['setup'] = EntryExitCalculator.calculate_short_setup(analysis, ob_a)
                except Exception as e:
                    logger.warning(f"خطا در محاسبه setup شورت برای {coin_score['coin']['symbol']}: {e}")

    # اعمال setup مناسب برای لیست لانگ
    for c in long_list:
        ensure_long_setup(c)

    # اگر لانگ کم بود، از بقیه پر کن
    if len(long_list) < config.TOP_LONG_COUNT:
        existing_symbols = {c['coin']['symbol'] for c in long_list}
        extra = [c for c in all_scored if c['coin']['symbol'] not in existing_symbols]
        extra.sort(key=lambda x: x['long_score'], reverse=True)
        for c in extra:
            c_copy = copy.deepcopy(c)
            ensure_long_setup(c_copy)
            long_list.append(c_copy)
            if len(long_list) >= config.TOP_LONG_COUNT:
                break

    # اعمال setup مناسب برای لیست شورت
    for c in short_list:
        ensure_short_setup(c)

    # اگر شورت کم بود، از بقیه پر کن
    if len(short_list) < config.TOP_SHORT_COUNT:
        existing_symbols = {c['coin']['symbol'] for c in short_list}
        extra = [c for c in all_scored if c['coin']['symbol'] not in existing_symbols]
        extra.sort(key=lambda x: x['short_score'], reverse=True)
        for c in extra:
            c_copy = copy.deepcopy(c)
            ensure_short_setup(c_copy)
            short_list.append(c_copy)
            if len(short_list) >= config.TOP_SHORT_COUNT:
                break

    top_signals_final = {'long': long_list, 'short': short_list}

    # ============ تولید گزارش ============
    logger.info("گام 7/7: تولید فایل Excel...")
    duration = time.time() - start_time
    scan_summary = {
        'total_scanned': len(coins),
        'successful': successful,
        'long_count': len(long_list),
        'short_count': len(short_list),
        'duration_sec': duration,
    }

    filepath = ReportGenerator.generate(top_signals_final, all_scored, scan_summary)

    # تولید گزارش PDF
    logger.info("تولید گزارش PDF...")
    try:
        pdf_filepath = generate_pdf(top_signals_final, all_scored, scan_summary)
        logger.info(f"فایل PDF تولید شد: {pdf_filepath}")
    except Exception as e:
        logger.warning(f"خطا در تولید PDF: {e}")
        pdf_filepath = None

    # ============ چاپ خلاصه ============
    print()
    print("=" * 70)
    print("خلاصه نتایج")
    print("=" * 70)
    print(f"تعداد کوین‌های اسکن شده: {len(coins)}")
    print(f"تحلیل‌های موفق: {successful}")
    print(f"مدت زمان: {duration:.1f} ثانیه")
    print()

    print(f"\n--- 10 پیشنهاد لانگ برتر ---")
    for i, s in enumerate(long_list[:10], 1):
        setup = s.get('setup', {})
        print(f"{i:2}. {s['coin']['base']:8} | امتیاز: {s['long_score']:5.1f} | "
              f"ورود: {setup.get('entry_price', '-')} | استاپ: {setup.get('stop_loss', '-')} | "
              f"هدف: {setup.get('target_2', '-')} | RR: {setup.get('risk_reward', '-')}")

    print(f"\n--- 10 پیشنهاد شورت برتر ---")
    for i, s in enumerate(short_list[:10], 1):
        setup = s.get('setup', {})
        print(f"{i:2}. {s['coin']['base']:8} | امتیاز: {s['short_score']:5.1f} | "
              f"ورود: {setup.get('entry_price', '-')} | استاپ: {setup.get('stop_loss', '-')} | "
              f"هدف: {setup.get('target_2', '-')} | RR: {setup.get('risk_reward', '-')}")

    print()
    print("=" * 70)
    print(f"فایل Excel: {filepath}")
    if pdf_filepath:
        print(f"فایل PDF:   {pdf_filepath}")
    print("=" * 70)

    return filepath


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("اجرای اسکنر توسط کاربر متوقف شد")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطای بحرانی: {e}", exc_info=True)
        sys.exit(1)
