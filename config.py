"""
تنظیمات مرکزی اسکنر کریپتو
Crypto Scanner Configuration
"""
import os
from datetime import datetime, timezone, timedelta

# ============ منطقه زمانی تهران (UTC+3:30) ============
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def tehran_now() -> datetime:
    """دریافت زمان فعلی تهران"""
    return datetime.now(TEHRAN_TZ)

def tehran_now_str(fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """دریافت زمان فعلی تهران به صورت رشته"""
    return tehran_now().strftime(fmt)

# ============ تنظیمات کلی ============
MIN_MARKET_CAP_USD = 100_000_000  # حداقل مارکت کپ 100 میلیون دلار
MAX_COINS_TO_SCAN = 80            # حداکثر تعداد کوین‌های اسکن شده (برای جلوگیری از محدودیت API)
TOP_LONG_COUNT = 10               # تعداد پیشنهادهای لانگ
TOP_SHORT_COUNT = 10              # تعداد پیشنهادهای شورت

# ============ تایم فریم‌ها (Top-Down) ============
# ترتیب تحلیل: 1d (24h) → 4h → 1h → 15m (ورود)
TIMEFRAMES = ['1d', '4h', '1h', '15m']

# تعداد کندل‌ها برای هر تایم فریم
CANDLE_LIMITS = {
    '1d': 120,   # ~4 ماه
    '4h': 180,   # ~30 روز
    '1h': 240,   # ~10 روز
    '15m': 200,  # ~50 ساعت
}

# ============ صرافی ============
# توجه: Binance این IP را مسدود کرده، از Bybit استفاده می‌کنیم
EXCHANGE_ID = 'bybit'
EXCHANGE_API_KEY = os.environ.get('BYBIT_API_KEY', '')
EXCHANGE_API_SECRET = os.environ.get('BYBIT_API_SECRET', '')

# ============ CoinGecko ============
COINGECKO_BASE_URL = 'https://api.coingecko.com/api/v3'

# ============ پارامترهای اندیکاتور ============
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

EMA_FAST = 20
EMA_SLOW = 50
EMA_TREND = 200

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

ATR_PERIOD = 14
VOLUME_MA_PERIOD = 20

# ============ پارامترهای امتیازدهی ============
SCORE_WEIGHTS = {
    'trend_alignment': 30,   # هماهنگی روند چند تایم فریم
    'momentum': 20,          # مومنتوم (RSI/MACD)
    'liquidity': 20,         # نقدینگی و جریان پول
    'volume': 15,            # حجم معاملات
    'structure': 15,         # ساختار قیمت (انباشت/شکست)
}

# ============ پارامترهای ورود و استاپ ============
# استایل Swing: استاپ‌های وسیع‌تر، بر اساس ساختار 4h، اهداف بزرگ‌تر
ATR_STOP_MULTIPLIER = 2.5    # ضریب استاپ لاس Swing (وسیع‌تر از Scalping)
ATR_TARGET_MULTIPLIER = 5.0  # ضریب هدف سود Swing (RR 1:2 برای target_2, 1:3 برای target_3)

# Swing: استفاده از ATR تایم فریم بالاتر (4h) برای استاپ
SWING_USE_4H_ATR = True      # استاپ بر اساس ATR 4h (نه 1h)
SWING_USE_DAILY_LEVELS = True  # استفاده از سطوح حمایت/مقاومت روزانه

# ============ لیست سیاه استیبل‌کوین‌ها و توکن‌های هم‌ارز ============
# این توکن‌ها قیمت ثابتی دارند یا قیمت آن‌ها با دارایی پایه هماهنگ است
# و برای معامله لانگ/شورت مناسب نیستند
STABLECOINS_BLACKLIST = {
    # استیبل‌کوین‌های USD
    'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP', 'FDUSD', 'USDD',
    'USDE', 'USD1', 'RLUSD', 'PYUSD', 'GUSD', 'PAX', 'SUSD', 'USDS',
    'FRAX', 'LUSD', 'SUSDE', 'USD0', 'USDY', 'USTC', 'CUSD', 'BSCUSD',
    'USDX', 'XUSD', 'DOLA', 'ZUSD', 'USDK', 'MIM', 'ALUSD', 'LUSD',
    'EURS', 'EURT', 'AEUR', 'GBPT', 'XEUR', 'TRYB', 'BIDR', 'IDRT',
    # توکن‌های استیبل مالی
    'STUSD', 'USDJ', 'HUSD', 'USDV', 'USDF', 'RUSD', 'USDO',
    # توکن‌های اهرمی/پایدار (Yield Bearing)
    'SUSDS', 'USDS', 'PAXG', 'XAUT',  # XAUT و PAXG هم به طلا متصلند
    # توکن‌های استیک شده که با دارایی پایه هماهنگند (اختیاری)
    'STETH', 'BBSOL', 'CBETH', 'WBETH', 'RETH', 'STBTC', 'WBTC',
}

# ============ تنظیمات تلگرام (اختیاری - برای ارسال خودکار) ============
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')  # chat_id یا channel username

# ============ مسیر خروجی ============
OUTPUT_DIR = '/home/z/my-project/download/crypto_scanner/output'
OUTPUT_FILE = 'crypto_signals_{timestamp}.xlsx'

# ایجاد پوشه خروجی
os.makedirs(OUTPUT_DIR, exist_ok=True)
