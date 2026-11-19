"""
پایش ساعتی بازار - سبک و سریع
Hourly Market Monitor

بررسی کوین‌های watchlist در هر ساعت
تشخیص تغییر وضعیت
ارسال هشدار فقط در صورت تغییر واقعی

این اسکریپت سبک است:
- فقط کوین‌های watchlist را بررسی می‌کند
- فقط قیمت و روند را چک می‌کند
- LLM فقط در صورت تغییر واقعی فراخوانی می‌شود
"""
import sys, os, time, logging

# تنظیم منطقه زمانی تهران
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
    """
    اجرای پایش ساعتی - سبک و سریع
    """
    start_time = time.time()
    logger.info("=" * 50)
    logger.info(f"پایش ساعتی بازار - {config.tehran_now_str()}")
    logger.info("=" * 50)

    # بارگذاری watchlist
    wl = WatchlistManager()
    active_coins = wl.get_active_coins()

    if not active_coins:
        logger.info("watchlist خالی است - چیزی برای پایش نیست")
        return True

    logger.info(f"تعداد کوین‌های فعال: {len(active_coins)}")

    # راه‌اندازی
    try:
        fetcher = DataFetcher()
    except Exception as e:
        logger.error(f"خطا در اتصال به صرافی: {e}")
        return False

    tg = TelegramSender()
    alerts_sent = 0

    # بررسی هر کوین
    for coin in active_coins:
        symbol = coin['symbol']
        try:
            # دریافت فقط قیمت فعلی (سبک)
            ticker = fetcher.fetch_ticker(symbol)
            if not ticker:
                continue

            current_price = ticker.get('last', 0)
            if current_price == 0:
                continue

            # دریافت روند 4H (فقط یک تایم فریم)
            trend_4h = None
            try:
                ohlcv_4h = fetcher.fetch_ohlcv(symbol, '4h', limit=60)
                if ohlcv_4h is not None and len(ohlcv_4h) >= 50:
                    df_4h = Indicators.compute_all(ohlcv_4h)
                    state_4h = Indicators.get_current_state(df_4h)
                    trend_4h = state_4h.get('trend_dir', 'خنثی')
            except Exception:
                pass  # اگر داده 4H در دسترس نبود، بدون trend ادامه بده

            # به‌روزرسانی و تشخیص تغییر
            alert = wl.update_coin_price(symbol, current_price, trend_4h)

            if alert:
                logger.info(f"  ⚡ هشدار برای {symbol}: {alert['old_status']} → {alert['new_status']}")
                if tg.is_configured():
                    tg.send_message(alert['message'])
                    alerts_sent += 1
                    time.sleep(1)  # جلوگیری از rate limit تلگرام

            logger.info(f"  {symbol}: {current_price} | {trend_4h or 'N/A'} | {coin['status']}")

            time.sleep(0.3)

        except Exception as e:
            logger.warning(f"خطا در پایش {symbol}: {e}")

    # پاک‌سازی کوین‌های منقضی
    wl.cleanup_expired()

    duration = time.time() - start_time
    logger.info(f"پایش کامل شد - {alerts_sent} هشدار ارسال شد - {duration:.1f}s")
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
