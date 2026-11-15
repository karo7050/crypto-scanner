"""
تست اتصال تلگرام
Telegram Connection Test

استفاده:
    # ابتدا متغیرهای محیطی را تنظیم کنید:
    export TELEGRAM_BOT_TOKEN='123456:ABC-DEF...'
    export TELEGRAM_CHAT_ID='123456789'  # یا '@channelname'

    # سپس اجرا:
    python3 test_telegram.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_sender import TelegramSender
import config


def main():
    print("=" * 60)
    print("تست اتصال به تلگرام")
    print("=" * 60)

    # بررسی پیکربندی
    print(f"\n1. بررسی پیکربندی:")
    print(f"   TELEGRAM_BOT_TOKEN: {'✓ تنظیم شده' if config.TELEGRAM_BOT_TOKEN else '✗ تنظیم نشده'}")
    print(f"   TELEGRAM_CHAT_ID:   {'✓ تنظیم شده' if config.TELEGRAM_CHAT_ID else '✗ تنظیم نشده'}")

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("\n❌ تلگرام پیکربندی نشده است!")
        print("\nراهنمای دریافت Bot Token:")
        print("  1. در تلگرام به @BotFather پیام دهید")
        print("  2. /newbot را بفرستید")
        print("  3. نام و username ربات را وارد کنید")
        print("  4. Bot Token را دریافت کنید (مثل: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ)")

        print("\nراهنمای دریافت Chat ID:")
        print("  روش 1 (پیام خصوصی):")
        print("    1. به ربات جدیدتان پیام بدهید")
        print("    2. به https://api.telegram.org/bot<TOKEN>/getUpdates بروید")
        print("    3. chat.id را از پاسخ پیدا کنید")
        print()
        print("  روش 2 (کانال):")
        print("    1. یک کانال تلگرام بسازید")
        print("    2. ربات را به عنوان admin به کانال اضافه کنید")
        print("    3. از username کانال استفاده کنید: @your_channel_name")

        print("\nتنظیم متغیرها:")
        print("  export TELEGRAM_BOT_TOKEN='your_token'")
        print("  export TELEGRAM_CHAT_ID='your_chat_id_or_channel'")
        print("\nیا اضافه کنید به فایل ~/.bashrc:")
        print("  echo 'export TELEGRAM_BOT_TOKEN=\"your_token\"' >> ~/.bashrc")
        print("  echo 'export TELEGRAM_CHAT_ID=\"your_chat_id\"' >> ~/.bashrc")
        print("  source ~/.bashrc")
        return False

    # تست اتصال
    print(f"\n2. تست اتصال...")
    tg = TelegramSender()

    if tg.test_connection():
        print("   ✓ اتصال موفق بود!")
        print("   ✓ پیام تست ارسال شد")
        print("\n✅ تلگرام آماده استفاده است!")
        print("   اسکنر هر روز ساعت 9 صبح و 4 بعد از ظهر (تهران)")
        print("   گزارش PDF و Excel را به تلگرام ارسال می‌کند.")
        return True
    else:
        print("   ✗ اتصال ناموفق بود!")
        print("\nبررسی کنید:")
        print("  - Bot Token صحیح است؟")
        print("  - Chat ID صحیح است؟")
        print("  - اگر کانال است، ربات admin شده؟")
        print("  - اگر چت خصوصی است، اول به ربات پیام داده‌اید؟")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
