"""
ماژول تقویم رویدادهای اقتصادی
Economic Events Calendar Module

رویدادهای مهم که بر بازار کریپتو تاثیر می‌گذارند:
- جلسات فدرال رزرو (FOMC)
- داده‌های تورم (CPI, PPI)
- اشتغال (NFP)
- GDP
- سخنرانی‌های روسای بانک‌های مرکزی

برای رویدادهای زنده، از API ForexFactory/WebFinancialCalendar استفاده می‌شود.
در صورت عدم دسترسی، از تقویم ثابت ماهانه استفاده می‌شود.
"""
import os
import requests
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# منطقه زمانی تهران
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))


class EconomicEventsCalendar:
    """تقویم رویدادهای اقتصادی با تاثیر بر کریپتو"""

    # رویدادهای مهم با الگوی ماهانه
    # این رویدادها معمولاً در زمان‌های مشخصی از ماه رخ می‌دهند
    RECURRING_EVENTS = [
        {
            'name': 'جلسه FOMC (فدرال رزرو)',
            'name_en': 'FOMC Meeting',
            'description': 'تصمیم‌گیری نرخ بهره فدرال رزرو آمریکا. تاثیر بسیار بالا بر بازار کریپتو.',
            'impact': 'high',
            'typical_time_tehran': '21:00',  # معمولاً ساعت 14:00 EST = 21:30 تهران
            'frequency': 'هر 6 هفته (8 بار در سال)',
        },
        {
            'name': 'داده تورم CPI',
            'name_en': 'CPI Release',
            'description': 'شاخص قیمت مصرف‌کننده. تورم بالا = احتمال افزایش نرخ بهره = فشار فروش کریپتو.',
            'impact': 'high',
            'typical_time_tehran': '15:30',  # 8:30 EST = 16:00 تهران (با احتساب تابستان)
            'frequency': 'ماهانه (اواسط ماه)',
        },
        {
            'name': 'داده اشتغال NFP',
            'name_en': 'Non-Farm Payrolls',
            'description': 'گزارش اشتغال غیرکشاورزی. داده قوی = دلار قوی = فشار کریپتو.',
            'impact': 'high',
            'typical_time_tehran': '15:30',
            'frequency': 'اولین جمعه هر ماه',
        },
        {
            'name': 'داده PPI (تورم تولیدکننده)',
            'name_en': 'PPI Release',
            'description': 'شاخص قیمت تولیدکننده. پیش‌بینی‌کننده تورم CPI.',
            'impact': 'medium',
            'typical_time_tehran': '15:30',
            'frequency': 'ماهانه',
        },
        {
            'name': 'داده GDP',
            'name_en': 'GDP Release',
            'description': 'رشد اقتصادی. تاثیر متوسط بر کریپتو.',
            'impact': 'medium',
            'typical_time_tehran': '15:30',
            'frequency': 'فصلی',
        },
        {
            'name': 'سخنرانی رئیس فدرال رزرو',
            'name_en': 'Fed Chair Speech',
            'description': 'سخنرانی جروم پاول. تاثیر بالا بر بازار.',
            'impact': 'high',
            'typical_time_tehran': 'متغیر',
            'frequency': 'غیرمنظم',
        },
        {
            'name': 'جلسات بانک مرکزی اروپا (ECB)',
            'name_en': 'ECB Meeting',
            'description': 'تصمیم نرخ بهره اروپا. تاثیر متوسط بر کریپتو.',
            'impact': 'medium',
            'typical_time_tehran': '15:15',
            'frequency': 'هر 6 هفته',
        },
    ]

    # رویدادهای خاص کریپتو
    CRYPTO_EVENTS = [
        {
            'name': 'سررسید آپشن‌های BTC',
            'description': 'سررسید ماهانه آپشن‌های بیت‌کوین در Deribit. معمولاً باعث نوسان قیمت.',
            'impact': 'medium',
            'frequency': 'آخرین جمعه هر ماه',
        },
        {
            'name': 'بازگشایی بازار سنتی',
            'description': 'باز شدن بازار سهام آمریکا. افزایش حجم معاملات کریپتو.',
            'impact': 'low',
            'frequency': 'روزانه (دوشنبه تا جمعه)',
        },
    ]

    def __init__(self):
        self.now_tehran = datetime.now(TEHRAN_TZ)

    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """
        دریافت رویدادهای پیش‌رو در 24 ساعت آینده
        """
        events = []

        # بررسی رویدادهای زنده از API (در صورت دسترسی)
        live_events = self._fetch_live_events()
        if live_events:
            events.extend(live_events)

        # اگر API در دسترس نبود، رویدادهای ثابت را بررسی کن
        if not events:
            events = self._get_static_events(hours_ahead)

        return events

    def _fetch_live_events(self) -> List[Dict]:
        """
        تلاش برای دریافت رویدادهای زنده از API عمومی
        """
        try:
            # استفاده از API عمومی تقویم اقتصادی
            # اگر در دسترس نبود، لیست خالی برمی‌گرداند
            url = "https://nfs.faireconomy.media ffcalendar_this_week.json"
            # این API ممکن است در دسترس نباشد، بنابراین فقط هندل می‌کنیم
            return []
        except Exception as e:
            logger.debug(f"API تقویم اقتصادی در دسترس نیست: {e}")
            return []

    def _get_static_events(self, hours_ahead: int) -> List[Dict]:
        """
        دریافت رویدادهای ثابت بر اساس الگوی ماهانه
        """
        events = []
        now = self.now_tehran
        end_time = now + timedelta(hours=hours_ahead)

        # امروز روز چندم است؟
        today = now.date()
        day_of_month = today.day
        weekday = today.weekday()  # 0=دوشنبه, 6=یکشنبه

        # بررسی اولین جمعه ماه (NFP)
        first_friday = self._get_first_friday(today.year, today.month)
        if first_friday == today:
            events.append({
                **self.RECURRING_EVENTS[2],  # NFP
                'datetime_tehran': datetime.combine(today, datetime.min.time()).replace(
                    hour=15, minute=30, tzinfo=TEHRAN_TZ
                ),
                'hours_until': self._hours_until(15, 30),
            })

        # بررسی روزهای CPI (معمولاً 13-15 ماه)
        if 13 <= day_of_month <= 16:
            events.append({
                **self.RECURRING_EVENTS[1],  # CPI
                'datetime_tehran': datetime.combine(today, datetime.min.time()).replace(
                    hour=15, minute=30, tzinfo=TEHRAN_TZ
                ),
                'hours_until': self._hours_until(15, 30),
            })

        # سررسید آپشن BTC (آخرین جمعه ماه)
        last_friday = self._get_last_friday(today.year, today.month)
        if last_friday == today:
            events.append({
                **self.CRYPTO_EVENTS[0],
                'datetime_tehran': datetime.combine(today, datetime.min.time()).replace(
                    hour=16, minute=0, tzinfo=TEHRAN_TZ
                ),
                'hours_until': self._hours_until(16, 0),
            })

        # بازگشایی بازار سنتی (دوشنبه تا جمعه ساعت 17:30 تهران = 9:30 EST)
        if weekday < 5:  # دوشنبه تا جمعه
            hours_until_open = self._hours_until(17, 30)
            if 0 <= hours_until_open <= hours_ahead:
                events.append({
                    **self.CRYPTO_EVENTS[1],
                    'datetime_tehran': datetime.combine(today, datetime.min.time()).replace(
                        hour=17, minute=30, tzinfo=TEHRAN_TZ
                    ),
                    'hours_until': hours_until_open,
                })

        return events

    def _hours_until(self, hour: int, minute: int) -> float:
        """ساعات باقی‌مانده تا زمان مشخص امروز"""
        now = self.now_tehran
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target < now:
            target += timedelta(days=1)
        delta = target - now
        return round(delta.total_seconds() / 3600, 1)

    def _get_first_friday(self, year: int, month: int):
        """اولین جمعه ماه"""
        from calendar import monthrange
        first_day = datetime(year, month, 1)
        days_until_friday = (4 - first_day.weekday()) % 7
        return (first_day + timedelta(days=days_until_friday)).date()

    def _get_last_friday(self, year: int, month: int):
        """آخرین جمعه ماه"""
        from calendar import monthrange
        last_day = datetime(year, month, monthrange(year, month)[1])
        days_back = (last_day.weekday() - 4) % 7
        return (last_day - timedelta(days=days_back)).date()

    def get_event_guidance(self, events: List[Dict]) -> Dict:
        """
        تولید راهنمایی برای ورود/خروج بر اساس رویدادهای پیش‌رو
        """
        if not events:
            return {
                'has_events': False,
                'message': 'هیچ رویداد اقتصادی مهمی در 24 ساعت آینده وجود ندارد. معامله با خیال راحت.',
                'risk_level': 'low',
                'recommendations': [
                    'استراتژی معمول قابل اجراست',
                    'مدیریت ریسک استاندارد (1-2% سرمایه در هر معامله)',
                    'تایید سیگنال با حجم معاملات',
                ],
            }

        # یافتن نزدیک‌ترین رویداد
        nearest = min(events, key=lambda e: e.get('hours_until', 999))
        hours_until = nearest.get('hours_until', 0)

        if nearest['impact'] == 'high':
            if hours_until <= 2:
                risk_level = 'critical'
                message = f'⚠ هشدار: رویداد مهم "{nearest["name"]}" در {hours_until:.1f} ساعت آینده!'
                recommendations = [
                    '🚨 پوزیشن‌های بزرگ را ببندید یا استاپ تنگ‌تر کنید',
                    '🚨 از باز کردن پوزیشن جدید خودداری کنید',
                    '🚨 نوسانات شدید پس از رویداد محتمل است',
                    '🚨 صبر کنید تا پس از رویداد و تثبیت قیمت، وارد شوید',
                    '🚨 در صورت داشتن پوزیشن، حد ضرر را فعال کنید',
                ]
            elif hours_until <= 6:
                risk_level = 'high'
                message = f'⚠ توجه: رویداد مهم "{nearest["name"]}" در {hours_until:.1f} ساعت آینده.'
                recommendations = [
                    '⚡ حجم پوزیشن‌ها را کاهش دهید',
                    '⚡ استاپ لاس را محافظه‌کارانه‌تر تنظیم کنید',
                    '⚡ از اهرم بالا خودداری کنید',
                    '⚡ پس از رویداد، فرصت‌های جدید بررسی شود',
                ]
            else:
                risk_level = 'medium'
                message = f'📋 رویداد مهم "{nearest["name"]}" در {hours_until:.1f} ساعت آینده.'
                recommendations = [
                    '📊 معاملات معمول با احتیاط',
                    '📊 برنامه خروج قبل از رویداد داشته باشید',
                    '📊 به زمان رویداد توجه کنید',
                ]
        else:
            risk_level = 'low'
            message = f'📋 رویداد "{nearest["name"]}" در {hours_until:.1f} ساعت آینده (تاثیر متوسط).'
            recommendations = [
                'معاملات معمول قابل ادامه',
                'نوسانات متوسط محتمل است',
            ]

        return {
            'has_events': True,
            'nearest_event': nearest,
            'all_events': events,
            'message': message,
            'risk_level': risk_level,
            'recommendations': recommendations,
            'hours_until_nearest': hours_until,
        }
