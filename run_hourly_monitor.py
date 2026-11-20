"""
پایش مداوم بازار - هر ساعت + هشدار تغییر
Continuous Market Monitor

بررسی می‌کند:
- وضعیت watchlist
- تغییر روند
- نزدیک ورود
- فعال‌سازی ورود
- استاپ خوردن
- target رسیدن
- فرصت جدید

در صورت تغییر واقعی، هشدار فوری به تلگرام
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
from core.watchlist_manager import WatchlistManager
from telegram_sender import TelegramSender
from multi_tf import MultiTimeframeAnalyzer
from indicators import Indicators
from price_action import PriceActionAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(config.OUTPUT_DIR, f'monitor_{config.tehran_now().strftime("%Y%m%d")}.log'),
            encoding='utf-8'
        ),
    ]
)
logger = logging.getLogger(__name__)


def run_hourly_monitor():
    """پایش مداوم بازار"""
    start_time = time.time()
    logger.info("=" * 50)
    logger.info(f"پایش مداوم بازار - {config.tehran_now_str()}")
    logger.info("=" * 50)

    wl = WatchlistManager()
    active_coins = wl.get_active_coins()

    if not active_coins:
        logger.info("watchlist خالی است")
        return True

    logger.info(f"تعداد کوین‌های فعال: {len(active_coins)}")

    try:
        fetcher = DataFetcher()
    except Exception as e:
        logger.error(f"خطا در اتصال: {e}")
        return False

    tg = TelegramSender()
    alerts_sent = 0

    for coin in active_coins:
        symbol = coin['symbol']
        try:
            ticker = fetcher.fetch_ticker(symbol)
            if not ticker:
                continue

            current_price = ticker.get('last', 0)
            if current_price == 0:
                continue

            # روند 4H
            trend_4h = None
            try:
                ohlcv_4h = fetcher.fetch_ohlcv(symbol, '4h', limit=60)
                if ohlcv_4h is not None and len(ohlcv_4h) >= 50:
                    df_4h = Indicators.compute_all(ohlcv_4h)
                    state_4h = Indicators.get_current_state(df_4h)
                    trend_4h = state_4h.get('trend_dir', 'خنثی')

                    # بررسی تغییر روند
                    old_direction = coin.get('direction', '')
                    if trend_4h == 'صعودی' and old_direction == 'SHORT':
                        logger.info(f"  ⚠ تغییر روند! {symbol}: صعودی شد ولی SHORT هست")
                    elif trend_4h == 'نزولی' and old_direction == 'LONG':
                        logger.info(f"  ⚠ تغییر روند! {symbol}: نزولی شد ولی LONG هست")
            except Exception:
                pass

            # به‌روزرسانی و هشدار
            alert = wl.update_coin_price(symbol, current_price, trend_4h)

            if alert:
                logger.info(f"  ⚡ هشدار: {symbol} - {alert['old_status']} → {alert['new_status']}")
                if tg.is_configured():
                    tg.send_message(alert['message'])
                    alerts_sent += 1
                    time.sleep(1)

            # نمایش وضعیت
            entry = coin.get('entry_price', 0)
            stop = coin.get('stop_loss', 0)
            dist_to_entry = abs(current_price - entry) / entry * 100 if entry > 0 else 0

            logger.info(f"  {symbol}: {current_price} | entry: {entry} | dist: {dist_to_entry:.1f}% | {coin['status']}")

            time.sleep(0.3)

        except Exception as e:
            logger.warning(f"خطا در پایش {symbol}: {e}")

    wl.cleanup_expired()

    duration = time.time() - start_time
    logger.info(f"پایش کامل - {alerts_sent} هشدار - {duration:.1f}s")
    return True


if __name__ == '__main__':
    try:
        run_hourly_monitor()
    except KeyboardInterrupt:
        logger.info("متوقف شد")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطای بحرانی: {e}", exc_info=True)
        sys.exit(1)
