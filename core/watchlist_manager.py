"""
مدیریت Watchlist و پیگیری کوین‌ها
Watchlist Manager -coin tracking and status management

ذخیره و به‌روزرسانی وضعیت کوین‌های معرفی شده در گزارش
تشخیص تغییر وضعیت
جلوگیری از هشدار تکراری
"""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import config
import logging

logger = logging.getLogger(__name__)

# مسیر فایل وضعیت
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'watchlist_state.json')

# زمان انقضا (48 ساعت)
EXPIRY_HOURS = 48


class WatchlistManager:
    """مدیریت watchlist و پیگیری وضعیت کوین‌ها"""

    def __init__(self):
        self.watchlist = self._load()
        self.alerts_sent = self.watchlist.get('_alerts_sent', [])

    def _load(self) -> Dict:
        """بارگذاری watchlist از فایل"""
        if os.path.exists(WATCHLIST_FILE):
            try:
                with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"خطا در بارگذاری watchlist: {e}")
        return {'coins': {}, '_alerts_sent': []}

    def _save(self):
        """ذخیره watchlist در فایل"""
        self.watchlist['_alerts_sent'] = self.alerts_sent
        try:
            with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.watchlist, f, ensure_ascii=False, indent=2)
            logger.info(f"Watchlist ذخیره شد: {len(self.watchlist.get('coins', {}))} کوین")
        except Exception as e:
            logger.error(f"خطا در ذخیره watchlist: {e}")

    def add_coin(self, symbol: str, direction: str, entry_price: float,
                 stop_loss: float, targets: List[float], signal_strength: str,
                 invalidation_conditions: List[str] = None):
        """
        افزودن کوین به watchlist
        """
        tehran_now = config.tehran_now_str()

        self.watchlist.setdefault('coins', {})[symbol] = {
            'symbol': symbol,
            'direction': direction,
            'entry_zone': [entry_price * 0.998, entry_price * 1.002],  # ±0.2%
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'targets': targets,
            'signal_strength': signal_strength,
            'status': 'WATCHING',
            'added_at': tehran_now,
            'last_update': tehran_now,
            'current_price': entry_price,
            'invalidation_conditions': invalidation_conditions or [
                f"قیمت زیر {stop_loss}",
                "تغییر روند 4H"
            ],
        }
        self._save()
        logger.info(f"کوین {symbol} به watchlist اضافه شد ({direction})")

    def remove_coin(self, symbol: str):
        """حذف کوین از watchlist"""
        if symbol in self.watchlist.get('coins', {}):
            del self.watchlist['coins'][symbol]
            self._save()
            logger.info(f"کوین {symbol} از watchlist حذف شد")

    def update_coin_price(self, symbol: str, current_price: float, trend_4h: str = None) -> Optional[Dict]:
        """
        به‌روزرسانی قیمت و تشخیص تغییر وضعیت
        برمی‌گرداند: هشدار در صورت تغییر وضعیت، None اگر تغییری نبود
        """
        coin = self.watchlist.get('coins', {}).get(symbol)
        if not coin:
            return None

        old_status = coin['status']
        old_price = coin.get('current_price', 0)
        coin['current_price'] = current_price
        coin['last_update'] = config.tehran_now_str()

        # تشخیص وضعیت جدید
        new_status = self._determine_status(coin, current_price, trend_4h)
        coin['status'] = new_status

        # بررسی تغییر وضعیت
        alert = None
        if new_status != old_status:
            alert = self._generate_alert(coin, old_status, new_status, current_price)
            if alert:
                alert_key = f"{symbol}_{new_status}_{config.tehran_now().strftime('%Y%m%d_%H')}"
                if alert_key not in self.alerts_sent:
                    self.alerts_sent.append(alert_key)
                    # نگهداری فقط 100 هشدار اخیر
                    if len(self.alerts_sent) > 100:
                        self.alerts_sent = self.alerts_sent[-100:]
                else:
                    alert = None  # هشدار تکراری

        # بررسی انقضا
        if new_status not in ['COMPLETED', 'INVALIDATED']:
            added_time = datetime.fromisoformat(coin['added_at'].replace('+03:30', '+03:30'))
            if (config.tehran_now() - added_time).total_seconds() > EXPIRY_HOURS * 3600:
                coin['status'] = 'EXPIRED'
                if alert is None:
                    alert = self._generate_alert(coin, old_status, 'EXPIRED', current_price)

        self._save()
        return alert

    def _determine_status(self, coin: Dict, current_price: float, trend_4h: str = None) -> str:
        """تشخیص وضعیت فعلی کوین"""
        direction = coin['direction']
        entry = coin['entry_price']
        stop = coin['stop_loss']
        targets = coin.get('targets', [])

        # بررسی استاپ
        if direction == 'LONG' and current_price <= stop:
            return 'INVALIDATED'
        if direction == 'SHORT' and current_price >= stop:
            return 'INVALIDATED'

        # بررسی target
        for t in targets:
            if direction == 'LONG' and current_price >= t:
                return 'COMPLETED'
            if direction == 'SHORT' and current_price <= t:
                return 'COMPLETED'

        # بررسی تغییر روند
        if trend_4h:
            if direction == 'LONG' and trend_4h == 'نزولی':
                return 'TREND_CHANGED'
            if direction == 'SHORT' and trend_4h == 'صعودی':
                return 'TREND_CHANGED'

        # بررسی نزدیک ورود
        entry_zone = coin.get('entry_zone', [entry * 0.998, entry * 1.002])
        if entry_zone[0] <= current_price <= entry_zone[1]:
            return 'ENTRY_CONFIRMED'

        # بررسی نزدیک شدن به entry
        dist_pct = abs(current_price - entry) / entry * 100
        if dist_pct < 2:
            return 'APPROACHING_ENTRY'

        return 'WATCHING'

    def _generate_alert(self, coin: Dict, old_status: str, new_status: str, price: float) -> Optional[Dict]:
        """تولید هشدار برای تغییر وضعیت"""
        status_emojis = {
            'WATCHING': '👁',
            'APPROACHING_ENTRY': '⚡',
            'ENTRY_CONFIRMED': '✅',
            'TREND_CHANGED': '⚠',
            'INVALIDATED': '❌',
            'EXPIRED': '⏰',
            'COMPLETED': '🎯',
        }

        status_names = {
            'WATCHING': 'تحت نظر',
            'APPROACHING_ENTRY': 'نزدیک ورود',
            'ENTRY_CONFIRMED': 'ورود تأیید شد',
            'TREND_CHANGED': 'تغییر روند',
            'INVALIDATED': 'ابطال شد',
            'EXPIRED': 'منقضی',
            'COMPLETED': 'تکمیل شد',
        }

        emoji = status_emojis.get(new_status, '📊')
        direction_emoji = '🟢' if coin['direction'] == 'LONG' else '🔴'

        alert = {
            'symbol': coin['symbol'],
            'direction': coin['direction'],
            'old_status': status_names.get(old_status, old_status),
            'new_status': status_names.get(new_status, new_status),
            'current_price': price,
            'entry_price': coin['entry_price'],
            'stop_loss': coin['stop_loss'],
            'targets': coin.get('targets', []),
            'emoji': emoji,
            'direction_emoji': direction_emoji,
        }

        # پیشنهاد اقدام
        if new_status == 'APPROACHING_ENTRY':
            alert['action'] = f"آماده شو برای ورود - قیمت به entry نزدیک شد"
        elif new_status == 'ENTRY_CONFIRMED':
            alert['action'] = f"ورود فعال شد - بررسی کن و وارد شو"
        elif new_status == 'INVALIDATED':
            alert['action'] = f"سناریو ابطال شد - از معامله صرف‌نظر کن"
        elif new_status == 'COMPLETED':
            alert['action'] = f"هدف رسید - سود بگیر"
        elif new_status == 'TREND_CHANGED':
            alert['action'] = f"روند تغییر کرد - پوزیشن را بررسی کن"
        elif new_status == 'EXPIRED':
            alert['action'] = f"فرصت منقضی شد - از watchlist حذف می‌شود"
        else:
            return None  # بدون هشدار

        alert['message'] = (
            f"{emoji} <b>هشدار Watchlist</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{alert['direction_emoji']} <b>{coin['symbol']}</b> | {coin['direction']}\n"
            f"💰 قیمت فعلی: {price}\n"
            f"📊 وضعیت: {alert['old_status']} → {alert['new_status']}\n"
            f"📍 ورود: {coin['entry_price']}\n"
            f"🔴 استاپ: {coin['stop_loss']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>پیشنهاد:</b> {alert['action']}"
        )

        return alert

    def get_active_coins(self) -> List[Dict]:
        """دریافت کوین‌های فعال در watchlist"""
        return [c for c in self.watchlist.get('coins', {}).values()
                if c['status'] not in ['COMPLETED', 'INVALIDATED', 'EXPIRED']]

    def get_all_coins(self) -> Dict:
        """دریافت همه کوین‌های watchlist"""
        return self.watchlist.get('coins', {})

    def cleanup_expired(self):
        """حذف کوین‌های منقضی/ابطال شده قدیمی"""
        coins = self.watchlist.get('coins', {})
        to_remove = []
        tehran_now = config.tehran_now()

        for symbol, coin in coins.items():
            if coin['status'] in ['COMPLETED', 'INVALIDATED', 'EXPIRED']:
                # حذف بعد از 24 ساعت از تکمیل/ابطال
                last_update = datetime.fromisoformat(coin['last_update'].replace('+03:30', '+03:30'))
                if (tehran_now - last_update).total_seconds() > 24 * 3600:
                    to_remove.append(symbol)

        for symbol in to_remove:
            del coins[symbol]

        if to_remove:
            self._save()
            logger.info(f"{len(to_remove)} کوین قدیمی از watchlist حذف شد")
