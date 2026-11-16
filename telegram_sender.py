"""
ماژول ارسال گزارش به تلگرام
Telegram Sender Module
- ارسال فایل PDF و Excel به کانال یا چت تلگرام
- ارسال پیمت خلاصه با امار و برترین سیگنال‌ها
"""
import os
import requests
import logging
from typing import Optional, Dict, List
from datetime import datetime
import config

logger = logging.getLogger(__name__)


class TelegramSender:
    """ارسال گزارش به تلگرام"""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.api_base = f'https://api.telegram.org/bot{self.bot_token}'

    def is_configured(self) -> bool:
        """بررسی اینکه آیا تلگرام پیکربندی شده است"""
        return bool(self.bot_token and self.chat_id)

    # ----------------- ارسال پیام متنی -----------------
    def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """
        ارسال پیام متنی به تلگرام
        """
        if not self.is_configured():
            logger.warning("تلگرام پیکربندی نشده. TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID را تنظیم کنید.")
            return False

        try:
            # تلگرام محدودیت 4096 کاراکتر دارد
            if len(text) > 4000:
                # تقسیم به چند پیام
                chunks = self._split_text(text, 4000)
                for chunk in chunks:
                    self._send_single_message(chunk, parse_mode)
                return True
            else:
                return self._send_single_message(text, parse_mode)
        except Exception as e:
            logger.error(f"خطا در ارسال پیام تلگرام: {e}")
            return False

    def _send_single_message(self, text: str, parse_mode: str) -> bool:
        """ارسال یک پیام واحد"""
        try:
            url = f'{self.api_base}/sendMessage'
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True,
            }
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                return True
            else:
                logger.error(f"خطای تلگرام {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"خطا در ارسال: {e}")
            return False

    # ----------------- ارسال فایل -----------------
    def send_document(self, file_path: str, caption: str = '') -> bool:
        """
        ارسال فایل (PDF/Excel) به تلگرام
        """
        if not self.is_configured():
            logger.warning("تلگرام پیکربندی نشده.")
            return False

        if not os.path.exists(file_path):
            logger.error(f"فایل یافت نشد: {file_path}")
            return False

        try:
            url = f'{self.api_base}/sendDocument'
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption[:1024] if caption else '',  # محدودیت caption
                }
                resp = requests.post(url, files=files, data=data, timeout=120)

            if resp.status_code == 200:
                logger.info(f"فایل ارسال شد: {file_path}")
                return True
            else:
                logger.error(f"خطای ارسال فایل {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"خطا در ارسال فایل: {e}")
            return False

    # ----------------- ارسال گزارش کامل اسکنر -----------------
    def send_scan_report(self, pdf_path: str, excel_path: str, signals: Dict, scan_summary: Dict, event_guidance: Dict = None) -> bool:
        """
        ارسال کامل گزارش اسکنر:
        1. پیام هشدار رویداد (در صورت وجود رویداد مهم)
        2. پیام خلاصه با برترین سیگنال‌ها + تحلیل حجم
        3. فایل PDF
        4. فایل Excel
        """
        if not self.is_configured():
            logger.warning("تلگرام پیکربندی نشده. گزارش ارسال نشد.")
            return False

        success = True

        # 1. ارسال هشدار رویداد اقتصادی (در صورت وجود)
        if event_guidance and event_guidance.get('has_events'):
            event_msg = self._build_event_message(event_guidance)
            if event_msg:
                self.send_message(event_msg)
                # اگر رویداد بحرانی است، مکث کوتاه
                if event_guidance.get('risk_level') == 'critical':
                    import time
                    time.sleep(1)

        # 2. ارسال پیام خلاصه با تحلیل حجم
        summary_msg = self._build_summary_message(signals, scan_summary, event_guidance)
        if not self.send_message(summary_msg):
            success = False

        # 3. ارسال فایل PDF
        pdf_caption = f"📊 گزارش اسکنر کریپتو - {config.tehran_now().strftime('%H:%M')} (تهران)"
        if event_guidance and event_guidance.get('has_events'):
            nearest = event_guidance.get('nearest_event', {})
            if nearest:
                pdf_caption += f"\n⚠ رویداد پیش‌رو: {nearest.get('name', '')}"
        if not self.send_document(pdf_path, pdf_caption):
            success = False

        # 4. ارسال فایل Excel
        if os.path.exists(excel_path):
            excel_caption = f"📋 فایل Excel - {config.tehran_now().strftime('%H:%M')}"
            if not self.send_document(excel_path, excel_caption):
                pass

        return success

    # ----------------- ساخت پیام رویداد -----------------
    @staticmethod
    def _build_event_message(event_guidance: Dict) -> str:
        """ساخت پیام هشدار رویداد اقتصادی"""
        if not event_guidance or not event_guidance.get('has_events'):
            return ''

        risk_level = event_guidance.get('risk_level', 'low')
        message = event_guidance.get('message', '')
        recommendations = event_guidance.get('recommendations', [])
        nearest = event_guidance.get('nearest_event', {})
        hours_until = event_guidance.get('hours_until_nearest', 0)

        # انتخاب ایموجی بر اساس سطح ریسک
        if risk_level == 'critical':
            emoji = '🚨'
        elif risk_level == 'high':
            emoji = '⚠'
        elif risk_level == 'medium':
            emoji = '📋'
        else:
            emoji = 'ℹ'

        msg = []
        msg.append(f"{emoji} <b>هشدار رویداد اقتصادی</b>")
        msg.append(f"━━━━━━━━━━━━━━━━━━━━")
        msg.append(f"<b>{message}</b>")
        if nearest:
            msg.append(f"")
            msg.append(f"📅 رویداد: <b>{nearest.get('name', '')}</b>")
            msg.append(f"⏰ زمان: {nearest.get('typical_time_tehran', 'نامشخص')} (تهران)")
            msg.append(f"📊 تاثیر: {nearest.get('impact', '').upper()}")
            msg.append(f"🕐 تا رویداد: <b>{hours_until:.1f} ساعت</b>")
            msg.append(f"📝 {nearest.get('description', '')}")
        msg.append("")
        msg.append(f"<b>توصیه‌ها:</b>")
        for rec in recommendations:
            msg.append(f"  {rec}")
        msg.append("")
        msg.append("━━━━━━━━━━━━━━━━━━━━")

        return '\n'.join(msg)

    # ----------------- ساخت پیام خلاصه -----------------
    @staticmethod
    def _build_summary_message(signals: Dict, scan_summary: Dict, event_guidance: Dict = None) -> str:
        """ساخت پیام خلاصه با برترین سیگنال‌ها + تحلیل حجم (HTML)"""
        now = config.tehran_now()
        msg = []
        msg.append(f"<b>📊 گزارش اسکنر کریپتو</b>")
        msg.append(f"🕐 {now.strftime('%Y-%m-%d %H:%M')} (تهران)")
        msg.append(f"━━━━━━━━━━━━━━━━━━━━")
        msg.append(f"🔢 کوین‌های اسکن شده: <b>{scan_summary.get('total_scanned', 0)}</b>")
        msg.append(f"✅ تحلیل‌های موفق: <b>{scan_summary.get('successful', 0)}</b>")
        msg.append(f"⏱ مدت زمان: <b>{round(scan_summary.get('duration_sec', 0), 1)}s</b>")
        msg.append(f"💰 حداقل مارکت کپ: <b>$100M</b>")
        msg.append("")

        # برترین لانگ‌ها
        long_signals = signals.get('long', [])
        if long_signals:
            msg.append("🟢 <b>برترین سیگنال‌های لانگ</b>")
            msg.append("━━━━━━━━━━━━━━━━━━━━")
            for i, s in enumerate(long_signals[:5], 1):
                coin = s.get('coin', {})
                setup = s.get('setup', {})
                score = s.get('long_score', 0)
                vol_entry = s.get('volume_entry', {})
                entry = TelegramSender._fmt_price(setup.get('entry_price', 0))
                stop = TelegramSender._fmt_price(setup.get('stop_loss', 0))
                target = TelegramSender._fmt_price(setup.get('target_2', 0))
                stop_pct = setup.get('stop_pct', 0)

                # تحلیل حجم و OI/Funding
                vol_emoji = ''
                vol_info = ''
                if vol_entry:
                    entry_signal = vol_entry.get('entry_signal', '')
                    h1_vol = vol_entry.get('1h', {}).get('vol_ratio', 1)
                    m15_vol = vol_entry.get('15m', {}).get('vol_ratio', 1)
                    if 'ورود قوی' in entry_signal:
                        vol_emoji = '🟢'
                    elif 'هشدار' in entry_signal:
                        vol_emoji = '🔴'
                    elif 'احتیاط' in entry_signal:
                        vol_emoji = '🟡'
                    else:
                        vol_emoji = '⚪'
                    vol_info = f"\n   {vol_emoji} حجم 1h: {h1_vol}x | 15m: {m15_vol}x"

                # OI و Funding
                oi_info = ''
                oi_data = s.get('_oi_data')
                if oi_data and oi_data.get('oi_usd'):
                    funding_rate = oi_data.get('funding_rate', 0)
                    funding_emoji = '🔴' if funding_rate > 0.0003 else '🟢' if funding_rate < -0.0001 else '⚪'
                    oi_info = f"\n   {funding_emoji} OI: ${oi_data['oi_usd']/1e6:.0f}M | Funding: {funding_rate*100:.4f}%"

                # Volume Flow (ورود/خروج پول)
                flow_info = ''
                flow_data = s.get('_flow_data')
                if flow_data:
                    net = flow_data.get('net_flow_24h_usd', 0)
                    if abs(net) >= 1e6:
                        net_str = f"${net/1e6:.1f}M"
                    elif abs(net) >= 1e3:
                        net_str = f"${net/1e3:.0f}K"
                    else:
                        net_str = f"${net:.0f}"
                    flow_emoji = '🟢' if net > 0 else '🔴' if net < 0 else '⚪'
                    flow_info = f"\n   {flow_emoji} Flow 24h: {net_str} ({flow_data.get('direction_en', '')})"

                # BTC pair (قدرت نسبت به بیت‌کوین)
                btc_info = ''
                btc_data = s.get('_btc_data')
                if btc_data and btc_data.get('available'):
                    btc_score = btc_data.get('btc_score', 0)
                    change_4h = btc_data.get('4h', {}).get('change_24h_vs_btc_pct', 0)
                    if btc_score > 0:
                        btc_emoji = '💪'  # قوی‌تر از BTC
                        btc_info = f"\n   {btc_emoji} vs BTC: {change_4h:+.1f}% (قوی‌تر)"
                    elif btc_score < 0:
                        btc_emoji = '📉'  # ضعیف‌تر از BTC
                        btc_info = f"\n   {btc_emoji} vs BTC: {change_4h:+.1f}% (ضعیف‌تر)"

                msg.append(
                    f"{i}. {vol_emoji} <b>{coin.get('base', '')}</b> | امتیاز: {score:.1f}\n"
                    f"   📍 ورود: {entry} ({setup.get('entry_strategy', '')[:40]})\n"
                    f"   🔴 استاپ: {stop} ({stop_pct}%) - {setup.get('stop_reason', '')[:50]}\n"
                    f"   🎯 هدف: {target} (RR 1:3) - {setup.get('target_2_reason', '')[:50]}{vol_info}{oi_info}{flow_info}{btc_info}"
                )
            msg.append("")

        # برترین شورت‌ها
        short_signals = signals.get('short', [])
        if short_signals:
            msg.append("🔴 <b>برترین سیگنال‌های شورت</b>")
            msg.append("━━━━━━━━━━━━━━━━━━━━")
            for i, s in enumerate(short_signals[:5], 1):
                coin = s.get('coin', {})
                setup = s.get('setup', {})
                score = s.get('short_score', 0)
                vol_entry = s.get('volume_entry', {})
                entry = TelegramSender._fmt_price(setup.get('entry_price', 0))
                stop = TelegramSender._fmt_price(setup.get('stop_loss', 0))
                target = TelegramSender._fmt_price(setup.get('target_2', 0))
                stop_pct = setup.get('stop_pct', 0)

                # تحلیل حجم و OI/Funding
                vol_emoji = ''
                vol_info = ''
                if vol_entry:
                    entry_signal = vol_entry.get('entry_signal', '')
                    h1_vol = vol_entry.get('1h', {}).get('vol_ratio', 1)
                    m15_vol = vol_entry.get('15m', {}).get('vol_ratio', 1)
                    if 'ورود قوی' in entry_signal:
                        vol_emoji = '🟢'
                    elif 'هشدار' in entry_signal:
                        vol_emoji = '🔴'
                    elif 'احتیاط' in entry_signal:
                        vol_emoji = '🟡'
                    else:
                        vol_emoji = '⚪'
                    vol_info = f"\n   {vol_emoji} حجم 1h: {h1_vol}x | 15m: {m15_vol}x"

                # OI و Funding
                oi_info = ''
                oi_data = s.get('_oi_data')
                if oi_data and oi_data.get('oi_usd'):
                    funding_rate = oi_data.get('funding_rate', 0)
                    funding_emoji = '🔴' if funding_rate > 0.0003 else '🟢' if funding_rate < -0.0001 else '⚪'
                    oi_info = f"\n   {funding_emoji} OI: ${oi_data['oi_usd']/1e6:.0f}M | Funding: {funding_rate*100:.4f}%"

                # Volume Flow
                flow_info = ''
                flow_data = s.get('_flow_data')
                if flow_data:
                    net = flow_data.get('net_flow_24h_usd', 0)
                    if abs(net) >= 1e6:
                        net_str = f"${net/1e6:.1f}M"
                    elif abs(net) >= 1e3:
                        net_str = f"${net/1e3:.0f}K"
                    else:
                        net_str = f"${net:.0f}"
                    flow_emoji = '🟢' if net > 0 else '🔴' if net < 0 else '⚪'
                    flow_info = f"\n   {flow_emoji} Flow 24h: {net_str} ({flow_data.get('direction_en', '')})"

                # BTC pair
                btc_info = ''
                btc_data = s.get('_btc_data')
                if btc_data and btc_data.get('available'):
                    btc_score = btc_data.get('btc_score', 0)
                    change_4h = btc_data.get('4h', {}).get('change_24h_vs_btc_pct', 0)
                    if btc_score > 0:
                        btc_emoji = '💪'
                        btc_info = f"\n   {btc_emoji} vs BTC: {change_4h:+.1f}% (قوی‌تر)"
                    elif btc_score < 0:
                        btc_emoji = '📉'
                        btc_info = f"\n   {btc_emoji} vs BTC: {change_4h:+.1f}% (ضعیف‌تر)"

                msg.append(
                    f"{i}. {vol_emoji} <b>{coin.get('base', '')}</b> | امتیاز: {score:.1f}\n"
                    f"   📍 ورود: {entry} ({setup.get('entry_strategy', '')[:40]})\n"
                    f"   🔴 استاپ: {stop} ({stop_pct}%) - {setup.get('stop_reason', '')[:50]}\n"
                    f"   🎯 هدف: {target} (RR 1:3) - {setup.get('target_2_reason', '')[:50]}{vol_info}{oi_info}{flow_info}{btc_info}"
                )
            msg.append("")

        # راهنمای تحلیل
        msg.append("━━━━━━━━━━━━━━━━━━━━")
        msg.append("📊 <b>راهنمای تحلیل:</b>")
        msg.append("  🟢 حجم بالا / Funding منفی / Flow مثبت = تایید ورود")
        msg.append("  💪 قوی‌تر از BTC = ارز از بیت‌کوین بهتر عمل می‌کند")
        msg.append("  📉 ضعیف‌تر از BTC = ارز از بیت‌کوین بدتر عمل می‌کند")
        msg.append("  🟡 حجم متوسط = احتیاط")
        msg.append("  🔴 حجم کم / Funding مثبت / Flow منفی = هشدار")
        msg.append("  ⚪ خنثی")

        # رویداد اقتصادی
        if event_guidance and event_guidance.get('has_events'):
            msg.append("")
            risk = event_guidance.get('risk_level', 'low')
            risk_emoji = {'critical': '🚨', 'high': '⚠', 'medium': '📋', 'low': 'ℹ'}.get(risk, 'ℹ')
            msg.append(f"{risk_emoji} <b>رویداد پیش‌رو:</b> {event_guidance.get('message', '')}")
        else:
            msg.append("")
            msg.append("✅ هیچ رویداد مهمی در 24 ساعت آینده وجود ندارد")

        msg.append("")
        msg.append("📋 جزئیات کامل در فایل PDF ضمیمه")
        msg.append("⚠ این گزارش تحلیلی است، نه توصیه سرمایه‌گذاری")

        return '\n'.join(msg)

    @staticmethod
    def _fmt_price(price) -> str:
        """فرمت‌بندی قیمت"""
        if price is None or price == 0:
            return '-'
        if price >= 1000:
            return f'{price:,.2f}'
        elif price >= 1:
            return f'{price:.4f}'
        elif price >= 0.01:
            return f'{price:.5f}'
        else:
            return f'{price:.8f}'

    @staticmethod
    def _split_text(text: str, max_length: int) -> List[str]:
        """تقسیم متن طولانی به چانک‌ها"""
        chunks = []
        lines = text.split('\n')
        current = ''
        for line in lines:
            if len(current) + len(line) + 1 > max_length:
                chunks.append(current)
                current = line
            else:
                current = current + '\n' + line if current else line
        if current:
            chunks.append(current)
        return chunks

    # ----------------- تست اتصال -----------------
    def test_connection(self) -> bool:
        """تست اتصال به تلگرام"""
        if not self.is_configured():
            return False
        try:
            url = f'{self.api_base}/getMe'
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                bot_info = resp.json()
                if bot_info.get('ok'):
                    bot_name = bot_info['result']['username']
                    logger.info(f"ربات تلگرام متصل: @{bot_name}")
                    # ارسال پیام تست
                    test_msg = "✅ تست اتصال موفق بود. اسکنر کریپتو آماده ارسال گزارش است."
                    return self.send_message(test_msg)
            return False
        except Exception as e:
            logger.error(f"خطا در تست اتصال: {e}")
            return False
