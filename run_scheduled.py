"""
اسکریپت اجرای زمان‌بندی‌شده اسکنر کریپتو
Scheduled Runner - اجرای کامل اسکن + ارسال به تلگرام

استفاده:
    python3 run_scheduled.py

زمان‌بندی پیشنهادی (Cron):
    9 صبح و 4 بعد از ظهر به وقت تهران (UTC+3:30)
    9:00 Tehran = 5:30 UTC
    16:00 Tehran = 12:30 UTC

    # در crontab:
    30 5 * * * TZ='Asia/Tehran' /usr/bin/python3 /path/to/run_scheduled.py >> /path/to/log 2>&1
    30 12 * * * TZ='Asia/Tehran' /usr/bin/python3 /path/to/run_scheduled.py >> /path/to/log 2>&1
"""
import sys
import os
import time
import logging
from datetime import datetime, timezone, timedelta

# تنظیم منطقه زمانی تهران برای همه خروجی‌ها
os.environ['TZ'] = 'Asia/Tehran'
try:
    time.tzset()
except AttributeError:
    pass  # ویندوز tzset ندارد

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
from telegram_sender import TelegramSender
from events_calendar import EconomicEventsCalendar
from oi_funding import OIFundingAnalyzer
from news_analyzer import NewsAnalyzer
from volume_flow import VolumeFlowAnalyzer
from btc_benchmark import BTCBenchmarkAnalyzer
import copy

# تنظیم لاگینگ
log_file = os.path.join(
    config.OUTPUT_DIR,
    f'scheduled_{config.tehran_now().strftime("%Y%m%d")}.log'
)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)


def run_scan_and_send():
    """
    اجرای کامل:
    1. اسکن بازار
    2. تولید PDF و Excel
    3. ارسال به تلگرام
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"شروع اجرای زمان‌بندی‌شده: {config.tehran_now().strftime('%Y-%m-%d %H:%M:%S')} (تهران)")
    logger.info("=" * 60)

    # ============ راه‌اندازی ============
    fetcher = DataFetcher()

    # ============ دریافت لیست کوین‌ها ============
    logger.info("گام 1/7: دریافت لیست کوین‌ها...")
    coins = fetcher.fetch_top_market_cap_coins()
    if not coins:
        logger.error("هیچ کوینی یافت نشد.")
        return False

    logger.info(f"تعداد کوین‌ها برای اسکن: {len(coins)}")

    # ============ تحلیل هر کوین ============
    logger.info("گام 2-5: تحلیل همه کوین‌ها...")
    all_scored = []
    successful = 0

    # دریافت اخبار یک بار برای همه کوین‌ها (کش می‌شود)
    logger.info("دریافت اخبار از RSS feeds...")
    NewsAnalyzer.fetch_all_news(max_per_source=30)

    for i, coin in enumerate(coins, start=1):
        symbol = coin['symbol']
        base = coin['base']

        try:
            timeframes_data = fetcher.fetch_all_timeframes(symbol)
            if len(timeframes_data) < 3:
                continue

            analysis = MultiTimeframeAnalyzer.analyze_all(timeframes_data)
            order_book = fetcher.fetch_order_book(symbol)
            ob_analysis = LiquidityAnalyzer.analyze_order_book(order_book) if order_book else None

            # دریافت OI و Funding Rate از Bybit
            try:
                oi_data = OIFundingAnalyzer.fetch_oi_and_funding(symbol)
            except Exception as e:
                logger.debug(f"خطا در OI {symbol}: {e}")
                oi_data = None

            # دریافت اخبار مرتبط با کوین
            try:
                news_data = NewsAnalyzer.get_news_for_coin(base, coin.get('name', ''))
            except Exception as e:
                logger.debug(f"خطا در اخبار {base}: {e}")
                news_data = None

            # محاسبه Volume Flow (ورود/خروج پول) از داده 1h
            try:
                tf_1h_df = timeframes_data.get('1h')
                if tf_1h_df is not None:
                    flow_data = VolumeFlowAnalyzer.compute_flow(tf_1h_df)
                else:
                    flow_data = None
            except Exception as e:
                logger.debug(f"خطا در Volume Flow {base}: {e}")
                flow_data = None

            # تحلیل BTC pair (قدرت نسبت به بیت‌کوین)
            try:
                btc_pair_data = timeframes_data.get('_btc_pair')
                if btc_pair_data:
                    btc_data = BTCBenchmarkAnalyzer.analyze_btc_pair(btc_pair_data)
                else:
                    btc_data = {'available': False}
            except Exception as e:
                logger.debug(f"خطا در BTC pair {base}: {e}")
                btc_data = {'available': False}

            # امتیازدهی با همه داده‌ها
            score = SignalEngine.score_coin(coin, analysis, ob_analysis, oi_data, news_data, flow_data, btc_data)
            score['_analysis'] = analysis
            score['_ob_analysis'] = ob_analysis
            score['_oi_data'] = oi_data
            score['_news_data'] = news_data
            score['_flow_data'] = flow_data
            score['_btc_data'] = btc_data

            if score['long_score'] >= score['short_score']:
                score['setup'] = EntryExitCalculator.calculate_long_setup(analysis, ob_analysis)
            else:
                score['setup'] = EntryExitCalculator.calculate_short_setup(analysis, ob_analysis)

            all_scored.append(score)
            successful += 1
            logger.info(f"  [{i}/{len(coins)}] {base}: Long={score['long_score']} Short={score['short_score']}")

            time.sleep(0.3)

        except Exception as e:
            logger.warning(f"خطا در تحلیل {symbol}: {e}")
            continue

    if not all_scored:
        logger.error("تحلیلی انجام نشد.")
        return False

    # ============ انتخاب نهایی ============
    logger.info("گام 6/7: انتخاب 10 لانگ و 10 شورت...")
    top_signals = SignalEngine.select_top_signals(all_scored)

    long_list = [copy.deepcopy(c) for c in top_signals['long']]
    short_list = [copy.deepcopy(c) for c in top_signals['short']]

    def ensure_long_setup(coin_score):
        if not coin_score.get('setup') or coin_score['setup'].get('direction') != 'LONG':
            analysis = coin_score.get('_analysis')
            ob_a = coin_score.get('_ob_analysis')
            if analysis:
                try:
                    coin_score['setup'] = EntryExitCalculator.calculate_long_setup(analysis, ob_a)
                except Exception as e:
                    logger.warning(f"خطا در setup لانگ {coin_score['coin']['symbol']}: {e}")

    def ensure_short_setup(coin_score):
        if not coin_score.get('setup') or coin_score['setup'].get('direction') != 'SHORT':
            analysis = coin_score.get('_analysis')
            ob_a = coin_score.get('_ob_analysis')
            if analysis:
                try:
                    coin_score['setup'] = EntryExitCalculator.calculate_short_setup(analysis, ob_a)
                except Exception as e:
                    logger.warning(f"خطا در setup شورت {coin_score['coin']['symbol']}: {e}")

    for c in long_list:
        ensure_long_setup(c)

    if len(long_list) < config.TOP_LONG_COUNT:
        existing = {c['coin']['symbol'] for c in long_list}
        extra = [c for c in all_scored if c['coin']['symbol'] not in existing]
        extra.sort(key=lambda x: x['long_score'], reverse=True)
        for c in extra:
            c_copy = copy.deepcopy(c)
            ensure_long_setup(c_copy)
            long_list.append(c_copy)
            if len(long_list) >= config.TOP_LONG_COUNT:
                break

    for c in short_list:
        ensure_short_setup(c)

    if len(short_list) < config.TOP_SHORT_COUNT:
        existing = {c['coin']['symbol'] for c in short_list}
        extra = [c for c in all_scored if c['coin']['symbol'] not in existing]
        extra.sort(key=lambda x: x['short_score'], reverse=True)
        for c in extra:
            c_copy = copy.deepcopy(c)
            ensure_short_setup(c_copy)
            short_list.append(c_copy)
            if len(short_list) >= config.TOP_SHORT_COUNT:
                break

    top_signals_final = {'long': long_list, 'short': short_list}

    # ============ تحلیل حجم ورود برای هر سیگنال ============
    logger.info("تحلیل حجم معاملات 1h و 15m برای نقطه ورود...")
    for signal_list in [long_list, short_list]:
        for signal in signal_list:
            try:
                analysis = signal.get('_analysis')
                if analysis:
                    volume_entry = MultiTimeframeAnalyzer.analyze_volume_entry(analysis)
                    signal['volume_entry'] = volume_entry
            except Exception as e:
                logger.warning(f"خطا در تحلیل حجم: {e}")
                signal['volume_entry'] = {}

    # ============ دریافت رویدادهای اقتصادی ============
    logger.info("بررسی رویدادهای اقتصادی پیش‌رو...")
    calendar = EconomicEventsCalendar()
    events = calendar.get_upcoming_events(hours_ahead=24)
    event_guidance = calendar.get_event_guidance(events)
    logger.info(f"رویدادهای پیش‌رو: {len(events)} مورد | سطح ریسک: {event_guidance['risk_level']}")

    # ============ تولید گزارش ============
    logger.info("گام 7/7: تولید گزارش‌ها...")
    duration = time.time() - start_time
    scan_summary = {
        'total_scanned': len(coins),
        'successful': successful,
        'long_count': len(long_list),
        'short_count': len(short_list),
        'duration_sec': duration,
    }

    excel_path = ReportGenerator.generate(top_signals_final, all_scored, scan_summary)

    try:
        pdf_path = generate_pdf(top_signals_final, all_scored, scan_summary)
    except Exception as e:
        logger.error(f"خطا در تولید PDF: {e}")
        pdf_path = None

    logger.info(f"Excel: {excel_path}")
    if pdf_path:
        logger.info(f"PDF: {pdf_path}")

    # ============ ارسال به تلگرام ============
    logger.info("ارسال به تلگرام...")
    tg = TelegramSender()

    if not tg.is_configured():
        logger.warning("تلگرام پیکربندی نشده. فایل‌ها فقط ذخیره شدند.")
        logger.info("برای ارسال به تلگرام، متغیرهای زیر را تنظیم کنید:")
        logger.info("  export TELEGRAM_BOT_TOKEN='your_bot_token'")
        logger.info("  export TELEGRAM_CHAT_ID='your_chat_id'")
    else:
        if pdf_path:
            success = tg.send_scan_report(pdf_path, excel_path, top_signals_final, scan_summary, event_guidance)
            if success:
                logger.info("✓ گزارش با موفقیت به تلگرام ارسال شد")
            else:
                logger.error("✗ ارسال به تلگرام ناموفق بود")

    logger.info(f"اتمام. مدت زمان کل: {duration:.1f} ثانیه")
    return True


if __name__ == '__main__':
    try:
        run_scan_and_send()
    except KeyboardInterrupt:
        logger.info("متوقف شد توسط کاربر")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطای بحرانی: {e}", exc_info=True)
        sys.exit(1)
