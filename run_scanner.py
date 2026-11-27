"""
اجرای معماری جدید: اسکنر + مغز
Scanner + Brain Runner

جریان:
1. اسکنر تمام کوین‌ها را تحلیل می‌کند (Python - سریع)
2. مغز تصمیم‌های LONG/SHORT را بررسی می‌کند (LLM - هوشمند)
3. نتایج به تلگرام ارسال می‌شود
4. فرصت‌ها در watchlist ثبت می‌شوند
5. تصمیمات در memory ذخیره می‌شوند
"""
import sys, os, time, logging

os.environ['TZ'] = 'Asia/Tehran'
try:
    time.tzset()
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data_fetcher import DataFetcher
from scanner import UnifiedScanner
from brain import ReviewBrain
from chart_generator import ChartGenerator
from core.data_models import Decision
from telegram_sender import TelegramSender
from events_calendar import EconomicEventsCalendar
from news_agent import NewsAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(config.OUTPUT_DIR, f'scanner_{config.tehran_now().strftime("%Y%m%d")}.log'),
            encoding='utf-8'
        ),
    ]
)
logger = logging.getLogger(__name__)


def run():
    """اجرای کامل"""
    start = time.time()
    logger.info("=" * 60)
    logger.info(f"اسکنر + مغز - {config.tehran_now_str()}")
    logger.info("=" * 60)

    # 1. راه‌اندازی
    fetcher = DataFetcher()
    scanner = UnifiedScanner(fetcher)
    brain = ReviewBrain()
    tg = TelegramSender()

    # 2. دریافت کوین‌ها
    logger.info("گام 1: دریافت لیست کوین‌ها...")
    coins = fetcher.fetch_top_market_cap_coins()
    if not coins:
        logger.error("هیچ کوینی یافت نشد")
        return False
    logger.info(f"تعداد: {len(coins)}")

    # 3. اسکن
    logger.info("گام 2: اسکن بازار...")
    decisions = scanner.scan_market(coins)

    # 4. مغز بررسی می‌کند
    logger.info("گام 3: بررسی مغز...")
    for d in decisions:
        if d.decision in [Decision.LONG, Decision.SHORT]:
            d = brain.review(d)

    # 5. رویدادها
    logger.info("گام 4: رویدادهای اقتصادی...")
    cal = EconomicEventsCalendar()
    events = cal.get_upcoming_events(hours_ahead=24)
    event_guidance = cal.get_event_guidance(events)

    # 6. ارسال تلگرام
    logger.info("گام 5: ارسال به تلگرام...")
    duration = time.time() - start
    scan_summary = {
        'total_scanned': len(coins),
        'successful': len(decisions),
        'long_count': sum(1 for d in decisions if d.decision == Decision.LONG),
        'short_count': sum(1 for d in decisions if d.decision == Decision.SHORT),
        'duration_sec': duration,
    }
    logger.info(f"لانگ: {scan_summary['long_count']} | شورت: {scan_summary['short_count']}")

    if tg.is_configured():
        # ارسال گزارش متنی
        tg.send_multi_agent_report(decisions, scan_summary, event_guidance)
        logger.info("✓ گزارش متنی ارسال شد")

        # تولید و ارسال نمودار برای سیگنال‌های LONG/SHORT
        logger.info("گام 5b: تولید نمودارها...")
        for d in decisions:
            if d.decision in [Decision.LONG, Decision.SHORT] and d.entry_price > 0:
                try:
                    # دریافت داده برای نمودار
                    coin_info = next((c for c in coins if c['symbol'] == d.symbol), None)
                    if coin_info:
                        tf_data = fetcher.fetch_all_timeframes(d.symbol)
                        df_1h = tf_data.get('1h')
                        if df_1h is not None:
                            # دریافت Coinalyze data
                            from coinalyze_data import CoinalyzeData
                            ca_data = CoinalyzeData.get_current_data(coin_info['base'])

                            # تولید نمودار
                            chart_path = ChartGenerator.generate_chart(coin_info, d, df_1h, None, ca_data)
                            if chart_path and os.path.exists(chart_path):
                                # ارسال به تلگرام
                                direction_emoji = '🟢' if d.decision == Decision.LONG else '🔴'
                                caption = f"{direction_emoji} {d.symbol} | {d.decision.value} | اعتماد: {d.confidence:.0%}"
                                tg.send_document(chart_path, caption)
                                logger.info(f"  📊 نمودار {d.symbol} ارسال شد")
                                time.sleep(1)
                except Exception as e:
                    logger.warning(f"خطا در نمودار {d.symbol}: {e}")

    # 7. ثبت در watchlist
    logger.info("گام 6: به‌روزرسانی watchlist...")
    for d in decisions:
        if d.decision in [Decision.LONG, Decision.SHORT] and d.entry_price > 0:
            scanner.wl.add_coin(
                symbol=d.symbol,
                direction=d.decision.value,
                entry_price=d.entry_price,
                stop_loss=d.stop_loss,
                targets=[d.target_1, d.target_2, d.target_3],
                signal_strength=d.signal_strength,
            )
    logger.info(f"Watchlist: {len(scanner.wl.get_active_coins())} کوین فعال")

    # 8. ثبت در memory
    for d in decisions:
        if d.decision in [Decision.LONG, Decision.SHORT] and d.entry_price > 0:
            scanner.memory.add_decision(
                symbol=d.symbol,
                direction=d.decision.value,
                entry=d.entry_price,
                stop=d.stop_loss,
                targets=[d.target_1, d.target_2, d.target_3],
                confidence=d.confidence,
                reasoning=d.brain_reasoning,
            )

    # 9. اخبار
    logger.info("گام 7: اسکن اخبار...")
    try:
        news = NewsAgent()
        news.run()
    except Exception as e:
        logger.warning(f"اخبار: {e}")

    logger.info(f"اتمام - {duration:.1f}s")
    return True


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        logger.info("متوقف شد")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطا: {e}", exc_info=True)
        sys.exit(1)
