"""
زمان‌بند دائمی اسکنر کریپتو
Crypto Scanner Daemon Scheduler

این اسکریپت به‌صورت دائمی اجرا می‌شود و در زمان‌های مشخص:
  - 9:00 صبح (تهران)
  - 4:00 بعد از ظهر (تهران)
گزارش اسکنر را اجرا کرده و به تلگرام ارسال می‌کند.

استفاده:
    # اجرا در پس‌زمینه (background)
    nohup python3 scheduler_daemon.py > scheduler.log 2>&1 &

    # یا اجرا در screen/tmux
    python3 scheduler_daemon.py

    # برای توقف:
    # kill <PID>  یا  pkill -f scheduler_daemon

متغیرهای محیطی:
    TELEGRAM_BOT_TOKEN - توکن ربات تلگرام
    TELEGRAM_CHAT_ID - chat_id یا @channel_name
"""
import os
import sys
import time
import logging
import signal
from datetime import datetime, timezone, timedelta

# اضافه کردن مسیر پروژه
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============ بارگذاری فایل .env (در صورت وجود) ============
def load_env_file():
    """بارگذاری متغیرهای محیطی از فایل .env"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env_file()

# منطقه زمانی تهران (UTC+3:30)
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# زمان‌های اجرا (ساعت:دقیقه به وقت تهران)
SCHEDULE_TIMES = [
    (9, 0),    # 9:00 صبح
    (16, 0),   # 4:00 بعد از ظهر
]

# مسیر لاگ
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOG_DIR, f'scheduler_{datetime.now(TEHRAN_TZ).strftime("%Y%m%d")}.log'),
            encoding='utf-8'
        ),
    ]
)
logger = logging.getLogger(__name__)


class CryptoScannerScheduler:
    """زمان‌بند دائمی برای اجرای اسکنر"""

    def __init__(self):
        self.running = True
        self.last_run_date = None  # برای جلوگیری از اجرای مجدد در همان دقیقه
        self.last_run_times = {}   # تاریخ آخرین اجرا برای هر زمان

        # ثبت signal handler برای توقف تمیز
        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _handle_stop(self, signum, frame):
        """مدیریت سیگنال توقف"""
        logger.info(f"سیگنال توقف دریافت شد ({signum}). در حال توقف...")
        self.running = False

    def get_tehran_time(self) -> datetime:
        """دریافت زمان فعلی تهران"""
        return datetime.now(TEHRAN_TZ)

    def should_run_now(self) -> bool:
        """
        بررسی اینکه آیا الان زمان اجراست
        - ساعت باید یکی از زمان‌های تعریف شده باشد
        - دقیقه باید 0 باشد (با تلورانس 2 دقیقه)
        - در همان روز قبلاً اجرا نشده باشد
        """
        now = self.get_tehran_time()
        current_hour = now.hour
        current_minute = now.minute
        today_key = now.strftime('%Y-%m-%d')

        for scheduled_hour, scheduled_minute in SCHEDULE_TIMES:
            # بررسی تطابق ساعت و دقیقه (با تلورانس 2 دقیقه)
            if current_hour == scheduled_hour and current_minute <= 2:
                run_key = f"{today_key}_{scheduled_hour}:{scheduled_minute}"
                if run_key not in self.last_run_times:
                    self.last_run_times[run_key] = now
                    return True

        return False

    def run_scan(self):
        """اجرای اسکنر و ارسال به تلگرام"""
        tehran_time = self.get_tehran_time()
        logger.info("=" * 60)
        logger.info(f"شروع اسکن زمان‌بندی‌شده: {tehran_time.strftime('%Y-%m-%d %H:%M:%S')} (تهران)")
        logger.info("=" * 60)

        try:
            # ایمپورت داخل تابع برای جلوگیری از خطای circular import
            import run_scheduled
            success = run_scheduled.run_scan_and_send()

            if success:
                logger.info("✓ اسکن با موفقیت انجام شد و به تلگرام ارسال شد")
            else:
                logger.error("✗ اسکن با خطا مواجه شد")

        except Exception as e:
            logger.error(f"خطای بحرانی در اجرای اسکن: {e}", exc_info=True)

    def run_forever(self):
        """اجرای دائمی زمان‌بند"""
        tehran_time = self.get_tehran_time()
        logger.info("=" * 60)
        logger.info("زمان‌بند اسکنر کریپتو شروع به کار کرد")
        logger.info(f"زمان شروع: {tehran_time.strftime('%Y-%m-%d %H:%M:%S')} (تهران)")
        logger.info(f"زمان‌های اجرا: {SCHEDULE_TIMES}")
        logger.info("برای توقف: Ctrl+C یا kill <PID>")
        logger.info("=" * 60)

        # نمایش زمان اجرای بعدی
        self._log_next_run()

        while self.running:
            try:
                # بررسی زمان اجرا
                if self.should_run_now():
                    self.run_scan()
                    self._log_next_run()

                # چک هر 30 ثانیه
                time.sleep(30)

            except KeyboardInterrupt:
                logger.info("توقف توسط کاربر")
                break
            except Exception as e:
                logger.error(f"خطا در حلقه اصلی: {e}")
                time.sleep(60)  # در صورت خطا، 1 دقیقه صبر کن

        logger.info("زمان‌بند متوقف شد.")

    def _log_next_run(self):
        """نمایش زمان اجرای بعدی"""
        now = self.get_tehran_time()
        today_key = now.strftime('%Y-%m-%d')

        next_runs = []
        for hour, minute in SCHEDULE_TIMES:
            run_key = f"{today_key}_{hour}:{minute}"
            if run_key in self.last_run_times:
                # امروز اجرا شده، فردا
                tomorrow = now + timedelta(days=1)
                next_time = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                # امروز اجرا نشده
                scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if scheduled_today > now:
                    next_time = scheduled_today
                else:
                    # زمان امروز گذشته، فردا
                    tomorrow = now + timedelta(days=1)
                    next_time = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)

            next_runs.append(next_time)

        if next_runs:
            next_run = min(next_runs)
            delta = next_run - now
            hours_remaining = int(delta.total_seconds() // 3600)
            minutes_remaining = int((delta.total_seconds() % 3600) // 60)
            logger.info(
                f"اجرای بعدی: {next_run.strftime('%Y-%m-%d %H:%M')} (تهران) "
                f"- {hours_remaining}h {minutes_remaining}m تا اجرا"
            )


def main():
    """نقطه ورود"""
    scheduler = CryptoScannerScheduler()
    scheduler.run_forever()


if __name__ == '__main__':
    main()
