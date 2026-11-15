#!/bin/bash
# ============================================================
# اسکریپت راه‌اندازی GitHub Repository
# Setup Script for GitHub Repository
# ============================================================
# این اسکریپت به شما کمک می‌کند:
#   1. git را در پوشه پروژه راه‌اندازی کنید
#   2. فایل‌ها را آماده commit کنید
#   3. به GitHub متصل و push کنید
# ============================================================

set -e

# رنگ‌ها
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  راه‌اندازی GitHub Repository برای اسکنر کریپتو${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""

# مسیر پروژه
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${YELLOW}مسیر پروژه: $PROJECT_DIR${NC}"
echo ""

# بررسی git
if ! command -v git &> /dev/null; then
    echo -e "${RED}خطا: git نصب نیست${NC}"
    echo "نصب:"
    echo "  Ubuntu/Debian: sudo apt install git"
    echo "  Mac: brew install git"
    echo "  Windows: https://git-scm.com/download/win"
    exit 1
fi

echo -e "${GREEN}✓ git نصب است: $(git --version)${NC}"
echo ""

# مرحله 1: راه‌اندازی git
echo -e "${YELLOW}مرحله 1: راه‌اندازی git repository${NC}"
if [ ! -d ".git" ]; then
    git init
    echo -e "${GREEN}✓ git repository ایجاد شد${NC}"
else
    echo -e "${GREEN}✓ git repository از قبل وجود دارد${NC}"
fi
echo ""

# بررسی .gitignore
if [ ! -f ".gitignore" ]; then
    echo -e "${RED}خطا: فایل .gitignore وجود ندارد${NC}"
    exit 1
fi
echo -e "${GREEN}✓ فایل .gitignore وجود دارد${NC}"
echo ""

# مرحله 2: بررسی فایل‌های اصلی
echo -e "${YELLOW}مرحله 2: بررسی فایل‌های پروژه${NC}"
REQUIRED_FILES=(
    "config.py"
    "data_fetcher.py"
    "indicators.py"
    "liquidity.py"
    "multi_tf.py"
    "signal_engine.py"
    "entry_exit.py"
    "events_calendar.py"
    "report.py"
    "pdf_report.py"
    "telegram_sender.py"
    "run_scheduled.py"
    "requirements.txt"
    ".github/workflows/crypto-scanner.yml"
    "README.md"
)

ALL_OK=true
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = false ]; then
    echo -e "${RED}برخی فایل‌ها موجود نیستند!${NC}"
    exit 1
fi
echo ""

# مرحله 3: اطمینان از عدم وجود فایل .env
echo -e "${YELLOW}مرحله 3: بررسی امنیت${NC}"
if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠ فایل .env موجود است - در .gitignore قرار دارد و آپلود نخواهد شد${NC}"
    echo -e "${YELLOW}  توکن تلگرام در GitHub Secrets تنظیم خواهد شد${NC}"
fi
echo ""

# مرحله 4: افزودن فایل‌ها
echo -e "${YELLOW}مرحله 4: افزودن فایل‌ها به git${NC}"
git add -A
git status --short | head -20
echo ""

# مرحله 5: commit
echo -e "${YELLOW}مرحله 5: ایجاد commit${NC}"
git commit -m "Initial commit: Crypto Scanner with multi-timeframe analysis, volume analysis, economic events, Telegram integration" 2>/dev/null || echo -e "${YELLOW}commit از قبل وجود دارد${NC}"
echo ""

# مرحله 6: راهنمایی اتصال به GitHub
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  فایل‌ها آماده آپلود هستند!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "${YELLOW}مراحل بعدی:${NC}"
echo ""
echo -e "${YELLOW}1. در GitHub یک repository جدید بسازید:${NC}"
echo "   https://github.com/new"
echo "   - نام: crypto-scanner"
echo "   - Private (توصیه شده)"
echo "   - Create repository"
echo ""
echo -e "${YELLOW}2. دستورات زیر را اجرا کنید (با جایگزینی USERNAME):${NC}"
echo ""
echo -e "   ${GREEN}git remote add origin https://github.com/USERNAME/crypto-scanner.git${NC}"
echo -e "   ${GREEN}git branch -M main${NC}"
echo -e "   ${GREEN}git push -u origin main${NC}"
echo ""
echo -e "${YELLOW}3. تنظیم GitHub Secrets:${NC}"
echo "   در GitHub → Settings → Secrets and variables → Actions"
echo "   New Repository Secret:"
echo "     Name: TELEGRAM_BOT_TOKEN"
echo "     Value: [توکن ربات شما]"
echo "     Name: TELEGRAM_CHAT_ID"
echo "     Value: @your_channel_name"
echo ""
echo -e "${YELLOW}4. فعال‌سازی Actions:${NC}"
echo "   در GitHub → تب Actions → Enable workflows"
echo ""
echo -e "${YELLOW}5. تست:${NC}"
echo "   در تب Actions → Crypto Scanner → Run Workflow"
echo ""
echo -e "${GREEN}پس از این مراحل، هر 4 ساعت به‌صورت خودکار گزارش به تلگرام ارسال می‌شود!${NC}"
