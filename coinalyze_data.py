"""
ماژول Coinalyze - داده‌های مشتقات واقعی
Coinalyze Data Module

داده‌های واقعی از Coinalyze API:
- Open Interest (جاری + تاریخی)
- Funding Rate (جاری + پیش‌بینی)
- Long/Short Ratio
- Liquidations
- OHLCV با حجم خرید/فروش جداگانه

API Key از کاربر: رایگان، 40 درخواست/دقیقه
"""
import requests
import time
import logging
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)

API_KEY = os.environ.get('COINALYZE_API_KEY', '5ac34643-1e46-4018-8bee-62ba649f187b')
BASE_URL = 'https://api.coinalyze.net/v1'

# کش سیمبل‌ها
_symbol_cache = None


class CoinalyzeData:
    """دریافت داده مشتقات از Coinalyze"""

    @staticmethod
    def _get_symbols() -> List[Dict]:
        """دریافت لیست سیمبل‌های فیوچرز"""
        global _symbol_cache
        if _symbol_cache is not None:
            return _symbol_cache

        try:
            resp = requests.get(f'{BASE_URL}/future-markets', params={'api_key': API_KEY}, timeout=10)
            if resp.status_code == 200:
                _symbol_cache = resp.json()
                return _symbol_cache
        except Exception as e:
            logger.error(f"خطا در دریافت سیمبل‌ها: {e}")
        return []

    @staticmethod
    def find_symbol(base: str) -> Optional[str]:
        """
        پیدا کردن سیمبل Coinalyze برای یک ارز
        مثلا: BTC → BTCUSD_PERP.A (Binance) یا BTCUSDT.6 (Bybit)
        """
        symbols = CoinalyzeData._get_symbols()

        # اولویت: Binance > Bybit > OKX
        priority = ['A', '6', 'O']  # exchange codes

        for code in priority:
            for s in symbols:
                if s.get('base_asset') == base and s.get('is_perpetual') and s.get('exchange') == code:
                    if s.get('has_long_short_ratio_data'):
                        return s['symbol']

        # fallback: هر perpetual
        for s in symbols:
            if s.get('base_asset') == base and s.get('is_perpetual'):
                return s['symbol']

        return None

    @staticmethod
    def get_current_data(base: str) -> Dict:
        """
        دریافت همه داده‌های جاری برای یک ارز:
        - Open Interest
        - Funding Rate
        - Predicted Funding Rate
        - Long/Short Ratio
        """
        symbol = CoinalyzeData.find_symbol(base)
        if not symbol:
            return {'available': False}

        result = {'available': True, 'symbol': symbol}

        try:
            # 1. Open Interest
            resp = requests.get(f'{BASE_URL}/open-interest', params={
                'api_key': API_KEY, 'symbols': symbol, 'convert_to_usd': 'true'
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                oi_data = resp.json()[0]
                result['oi_value'] = float(oi_data.get('value', 0))
                result['oi_update'] = oi_data.get('update', 0)

            time.sleep(0.1)

            # 2. Funding Rate
            resp = requests.get(f'{BASE_URL}/funding-rate', params={
                'api_key': API_KEY, 'symbols': symbol
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                fr_data = resp.json()[0]
                result['funding_rate'] = float(fr_data.get('value', 0))

            time.sleep(0.1)

            # 3. Predicted Funding Rate
            resp = requests.get(f'{BASE_URL}/predicted-funding-rate', params={
                'api_key': API_KEY, 'symbols': symbol
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                pfr_data = resp.json()[0]
                result['predicted_funding_rate'] = float(pfr_data.get('value', 0))

            time.sleep(0.1)

            # 4. Long/Short Ratio (آخرین 1 ساعت)
            now = int(time.time())
            past = now - 7200  # 2 ساعت
            resp = requests.get(f'{BASE_URL}/long-short-ratio-history', params={
                'api_key': API_KEY, 'symbols': symbol,
                'interval': '1hour', 'from': past, 'to': now
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                ls_data = resp.json()[0]
                history = ls_data.get('history', [])
                if history:
                    latest = history[-1]
                    result['long_ratio'] = float(latest.get('l', 0))
                    result['short_ratio'] = float(latest.get('s', 0))
                    result['ls_ratio'] = float(latest.get('r', 0))

            # تحلیل
            result.update(CoinalyzeData._analyze(result))

        except Exception as e:
            logger.error(f"خطا در Coinalyze {base}: {e}")
            result['error'] = str(e)

        return result

    @staticmethod
    def get_oi_history(base: str, interval: str = '4hour', hours: int = 24) -> List[Dict]:
        """
        دریافت تاریخچه Open Interest
        برای تشخیص ورود/خروج پول
        """
        symbol = CoinalyzeData.find_symbol(base)
        if not symbol:
            return []

        now = int(time.time())
        past = now - (hours * 3600)

        try:
            resp = requests.get(f'{BASE_URL}/open-interest-history', params={
                'api_key': API_KEY, 'symbols': symbol,
                'interval': interval, 'from': past, 'to': now,
                'convert_to_usd': 'true'
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                return resp.json()[0].get('history', [])
        except Exception as e:
            logger.error(f"خطا در OI history {base}: {e}")
        return []

    @staticmethod
    def get_liquidations(base: str, interval: str = '1hour', hours: int = 24) -> List[Dict]:
        """
        دریافت تاریخچه لیکوییداسیون
        برای تشخیص فشار خرید/فروش
        """
        symbol = CoinalyzeData.find_symbol(base)
        if not symbol:
            return []

        now = int(time.time())
        past = now - (hours * 3600)

        try:
            resp = requests.get(f'{BASE_URL}/liquidation-history', params={
                'api_key': API_KEY, 'symbols': symbol,
                'interval': interval, 'from': past, 'to': now,
                'convert_to_usd': 'true'
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                return resp.json()[0].get('history', [])
        except Exception as e:
            logger.error(f"خطا در liquidations {base}: {e}")
        return []

    @staticmethod
    def _analyze(data: Dict) -> Dict:
        """تحلیل داده‌های Coinalyze"""
        analysis = {}

        # Funding Rate تحلیل
        fr = data.get('funding_rate', 0)
        if fr < -0.0005:
            analysis['funding_signal'] = 'قوی - شورت‌ها به لانگ‌ها پرداخت می‌کنند (احتمال کف)'
            analysis['funding_score'] = 2  # حمایت لانگ
        elif fr < -0.0001:
            analysis['funding_signal'] = 'ملایم منفی'
            analysis['funding_score'] = 1
        elif fr > 0.0005:
            analysis['funding_signal'] = 'قوی - لانگ‌ها به شورت‌ها پرداخت می‌کنند (احتمال سقف)'
            analysis['funding_score'] = -2  # حمایت شورت
        elif fr > 0.0001:
            analysis['funding_signal'] = 'ملایم مثبت'
            analysis['funding_score'] = -1
        else:
            analysis['funding_signal'] = 'متعادل'
            analysis['funding_score'] = 0

        # Long/Short Ratio تحلیل
        long_r = data.get('long_ratio', 0)
        short_r = data.get('short_ratio', 0)
        if long_r > 0 and short_r > 0:
            if short_r > 60:
                analysis['ls_signal'] = f'شورت‌ها غالب ({short_r:.0f}%) - ممکن است squeeze صعودی رخ دهد'
                analysis['ls_score'] = 1  # حمایت لانگ (squeeze)
            elif long_r > 60:
                analysis['ls_signal'] = f'لانگ‌ها غالب ({long_r:.0f}%) - ممکن است squeeze نزولی رخ دهد'
                analysis['ls_score'] = -1  # حمایت شورت
            else:
                analysis['ls_signal'] = f'متعادل (L:{long_r:.0f}% / S:{short_r:.0f}%)'
                analysis['ls_score'] = 0

        # OI تحلیل
        oi = data.get('oi_value', 0)
        if oi > 1_000_000_000:
            analysis['oi_signal'] = f'بسیار بالا (${oi/1e9:.1f}B) - نقدینگی قوی'
            analysis['oi_score'] = 2
        elif oi > 100_000_000:
            analysis['oi_signal'] = f'بالا (${oi/1e6:.0f}M) - نقدینگی مناسب'
            analysis['oi_score'] = 1
        elif oi > 10_000_000:
            analysis['oi_signal'] = f'متوسط (${oi/1e6:.0f}M)'
            analysis['oi_score'] = 0
        else:
            analysis['oi_signal'] = f'پایین (${oi/1e6:.0f}M) - ریسک نقدینگی'
            analysis['oi_score'] = -1

        return analysis
