"""
اسکریپت اجرای Multi-Agent System
Multi-Agent Crypto Scanner Runner

جریان:
1. دریافت لیست کوین‌ها
2. اجرای 6 ایجنت برای هر کوین
3. مغز مرکزی تصمیم نهایی می‌گیرد
4. ارسال نتایج به تلگرام
"""
import sys
import os
import time
import logging
from datetime import datetime

# تنظیم منطقه زمانی تهران
os.environ['TZ'] = 'Asia/Tehran'
try:
    time.tzset()
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data_fetcher import DataFetcher
from core.decision_engine import DecisionPipeline
from core.watchlist_manager import WatchlistManager
from core.data_models import Decision
from telegram_sender import TelegramSender
from events_calendar import EconomicEventsCalendar

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(config.OUTPUT_DIR, f'multi_agent_{config.tehran_now().strftime("%Y%m%d")}.log'),
            encoding='utf-8'
        ),
    ]
)
logger = logging.getLogger(__name__)


def run_multi_agent_scan():
    """اجرای کامل سیستم چند‌ایجنت"""
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"شروع سیستم Multi-Agent: {config.tehran_now_str()}")
    logger.info("=" * 60)

    # راه‌اندازی
    fetcher = DataFetcher()
    pipeline = DecisionPipeline(fetcher)
    tg = TelegramSender()

    # دریافت لیست کوین‌ها
    logger.info("گام 1: دریافت لیست کوین‌ها...")
    coins = fetcher.fetch_top_market_cap_coins()
    if not coins:
        logger.error("هیچ کوینی یافت نشد")
        return False

    logger.info(f"تعداد کوین‌ها: {len(coins)}")

    # اجرای pipeline
    logger.info("گام 2: اجرای 6 ایجنت برای هر کوین...")
    decisions = pipeline.analyze_market(coins)

    # رویدادهای اقتصادی
    logger.info("گام 3: بررسی رویدادهای اقتصادی...")
    calendar = EconomicEventsCalendar()
    events = calendar.get_upcoming_events(hours_ahead=24)
    event_guidance = calendar.get_event_guidance(events)

    # تولید و ارسال گزارش
    logger.info("گام 4: ارسال به تلگرام...")
    duration = time.time() - start_time

    scan_summary = {
        'total_scanned': len(coins),
        'successful': len(decisions),
        'long_count': sum(1 for d in decisions if d.decision.value == 'LONG'),
        'short_count': sum(1 for d in decisions if d.decision.value == 'SHORT'),
        'duration_sec': duration,
    }

    if tg.is_configured():
        success = tg.send_multi_agent_report(decisions, scan_summary, event_guidance)
        if success:
            logger.info("✓ گزارش Multi-Agent به تلگرام ارسال شد")
        else:
            logger.error("✗ ارسال ناموفق")

    # ثبت فرصت‌های تأیید شده در watchlist
    logger.info("گام 5: به‌روزرسانی watchlist...")
    wl = WatchlistManager()
    for d in decisions:
        if d.decision in [Decision.LONG, Decision.SHORT] and d.entry_price > 0:
            targets = [d.target_1, d.target_2, d.target_3]
            wl.add_coin(
                symbol=d.symbol,
                direction=d.decision.value,
                entry_price=d.entry_price,
                stop_loss=d.stop_loss,
                targets=targets,
                signal_strength=d.signal_strength,
            )
    logger.info(f"Watchlist به‌روز شد: {len(wl.get_active_coins())} کوین فعال")

    logger.info(f"اتمام. مدت: {duration:.1f}s")
    return True


if __name__ == '__main__':
    try:
        run_multi_agent_scan()
    except KeyboardInterrupt:
        logger.info("متوقف شد")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطای بحرانی: {e}", exc_info=True)
        sys.exit(1)
