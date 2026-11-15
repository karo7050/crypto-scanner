#!/bin/bash
# ============================================================
# راه‌اندازی زمان‌بندی خودکار اسکنر کریپتو
# Setup Cron Jobs for Crypto Scanner
# ============================================================
# این اسکریپت دو کار انجام می‌دهد:
#   1. ارسال گزارش به تلگرام هر روز ساعت 9 صبح و 4 بعد از ظهر (تهران)
#   2. استفاده از TZ='Asia/Tehran' برای اطمینان از زمان صحیح
# ============================================================

# مسیر پروژه (به‌روزرسانی کنید اگر در مسیر دیگری نصب شده)
SCANNER_DIR="/home/z/my-project/download/crypto_scanner"
PYTHON_BIN=$(which python3)

echo "============================================================"
echo "  راه‌اندازی زمان‌بندی اسکنر کریپتو"
echo "============================================================"
echo "  مسیر پروژه: $SCANNER_DIR"
echo "  پایتون: $PYTHON_BIN"
echo "  زمان‌بندی: 9:00 صبح و 16:00 بعد از ظهر (تهران)"
echo "============================================================"
echo ""

# بررسی وجود فایل اصلی
if [ ! -f "$SCANNER_DIR/run_scheduled.py" ]; then
    echo "خطا: فایل run_scheduled.py در مسیر $SCANNER_DIR یافت نشد"
    exit 1
fi

# ایجاد لاگ‌دایر
mkdir -p "$SCANNER_DIR/logs"

# مسیر فایل لاگ
LOG_FILE="$SCANNER_DIR/logs/cron_$(date +%Y%m%d).log"

# دستور cron
CRON_CMD="30 5 * * * TZ='Asia/Tehran' $PYTHON_BIN $SCANNER_DIR/run_scheduled.py >> $LOG_FILE 2>&1"
CRON_CMD2="30 12 * * * TZ='Asia/Tehran' $PYTHON_BIN $SCANNER_DIR/run_scheduled.py >> $LOG_FILE 2>&1"

# بررسی cron فعلی
echo "دستورات cron موجود:"
crontab -l 2>/dev/null | grep -i "crypto_scanner" || echo "  (هیچ موردی یافت نشد)"
echo ""

# افزودن به crontab
( crontab -l 2>/dev/null | grep -v "crypto_scanner/run_scheduled" ; echo "$CRON_CMD" ; echo "$CRON_CMD2" ) | crontab -

echo "✓ زمان‌بندی‌های زیر به crontab اضافه شدند:"
echo "  • 9:00 صبح (تهران) = 5:30 UTC"
echo "  • 4:00 بعد از ظهر (تهران) = 12:30 UTC"
echo ""
echo "دستورات cron نهایی:"
crontab -l | grep "crypto_scanner"
echo ""
echo "============================================================"
echo "  برای تست دستی:"
echo "  $PYTHON_BIN $SCANNER_DIR/run_scheduled.py"
echo ""
echo "  برای حذف زمان‌بندی:"
echo "  crontab -l | grep -v 'crypto_scanner' | crontab -"
echo "============================================================"
