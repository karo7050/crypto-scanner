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
        دریافت همه داده‌های جاری + تاریخی برای یک ارز:
        - Open Interest (جاری + تغییر 24h)
        - Funding Rate (جاری + پیش‌بینی)
        - Long/Short Ratio
        - Liquidations (24h)
        - Buy/Sell Volume (آخرین کندل)
        """
        symbol = CoinalyzeData.find_symbol(base)
        if not symbol:
            return {'available': False}

        result = {'available': True, 'symbol': symbol}
        now = int(time.time())
        past_24h = now - 86400
        past_2h = now - 7200

        try:
            # 1. Open Interest جاری
            resp = requests.get(f'{BASE_URL}/open-interest', params={
                'api_key': API_KEY, 'symbols': symbol, 'convert_to_usd': 'true'
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                oi_data = resp.json()[0]
                result['oi_value'] = float(oi_data.get('value', 0))
            time.sleep(0.1)

            # 2. OI History - تغییر 24h
            resp = requests.get(f'{BASE_URL}/open-interest-history', params={
                'api_key': API_KEY, 'symbols': symbol, 'interval': '4hour',
                'from': past_24h, 'to': now, 'convert_to_usd': 'true'
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                hist = resp.json()[0].get('history', [])
                if hist:
                    first = hist[0]
                    latest = hist[-1]
                    result['oi_24h_ago'] = float(first.get('o', 0))
                    result['oi_change_pct'] = ((latest['c'] - first['o']) / first['o'] * 100) if first['o'] > 0 else 0
                    # تشخیص ورود/خروج پول
                    if result['oi_change_pct'] > 5:
                        result['oi_flow'] = 'ورود پول قوی (+{:.1f}%)'.format(result['oi_change_pct'])
                    elif result['oi_change_pct'] > 0:
                        result['oi_flow'] = 'ورود پول ملایم (+{:.1f}%)'.format(result['oi_change_pct'])
                    elif result['oi_change_pct'] < -5:
                        result['oi_flow'] = 'خروج پول قوی ({:.1f}%)'.format(result['oi_change_pct'])
                    else:
                        result['oi_flow'] = 'خروج پول ملایم ({:.1f}%)'.format(result['oi_change_pct'])
            time.sleep(0.1)

            # 3. Funding Rate جاری
            resp = requests.get(f'{BASE_URL}/funding-rate', params={
                'api_key': API_KEY, 'symbols': symbol
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                result['funding_rate'] = float(resp.json()[0].get('value', 0))
            time.sleep(0.1)

            # 4. Predicted Funding Rate
            resp = requests.get(f'{BASE_URL}/predicted-funding-rate', params={
                'api_key': API_KEY, 'symbols': symbol
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                result['predicted_funding_rate'] = float(resp.json()[0].get('value', 0))
            time.sleep(0.1)

            # 5. Long/Short Ratio (آخرین 2 ساعت)
            resp = requests.get(f'{BASE_URL}/long-short-ratio-history', params={
                'api_key': API_KEY, 'symbols': symbol, 'interval': '1hour', 'from': past_2h, 'to': now
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                ls_data = resp.json()[0]
                history = ls_data.get('history', [])
                if history:
                    latest = history[-1]
                    result['long_ratio'] = float(latest.get('l', 0))
                    result['short_ratio'] = float(latest.get('s', 0))
            time.sleep(0.1)

            # 6. Liquidations (24h)
            resp = requests.get(f'{BASE_URL}/liquidation-history', params={
                'api_key': API_KEY, 'symbols': symbol, 'interval': '1hour',
                'from': past_24h, 'to': now, 'convert_to_usd': 'true'
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                liq = resp.json()[0].get('history', [])
                result['long_liquidations_24h'] = sum(h.get('l', 0) for h in liq)
                result['short_liquidations_24h'] = sum(h.get('s', 0) for h in liq)
                result['total_liquidations_24h'] = result['long_liquidations_24h'] + result['short_liquidations_24h']
            time.sleep(0.1)

            # 7. Buy/Sell Volume (آخرین کندل)
            resp = requests.get(f'{BASE_URL}/ohlcv-history', params={
                'api_key': API_KEY, 'symbols': symbol, 'interval': '1hour', 'from': past_2h, 'to': now
            }, timeout=10)
            if resp.status_code == 200 and resp.json():
                ohlcv = resp.json()[0].get('history', [])
                if ohlcv:
                    latest = ohlcv[-1]
                    total_vol = float(latest.get('v', 0))
                    buy_vol = float(latest.get('bv', 0))
                    result['buy_volume'] = buy_vol
                    result['sell_volume'] = total_vol - buy_vol
                    result['buy_pct'] = (buy_vol / total_vol * 100) if total_vol > 0 else 50
                    result['buy_tx'] = int(latest.get('btx', 0))
                    result['total_tx'] = int(latest.get('tx', 0))

            # تحلیل کامل
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
        """تحلیل کامل داده‌های Coinalyze"""
        analysis = {}

        # === Funding Rate ===
        fr = data.get('funding_rate', 0)
        predicted_fr = data.get('predicted_funding_rate', 0)
        if fr < -0.0005:
            analysis['funding_signal'] = f'منفی قوی ({fr*100:.4f}%) - شورت‌ها به لانگ‌ها پرداخت (احتمال کف)'
            analysis['funding_score'] = 2
        elif fr < -0.0001:
            analysis['funding_signal'] = f'منفی ملایم ({fr*100:.4f}%)'
            analysis['funding_score'] = 1
        elif fr > 0.0005:
            analysis['funding_signal'] = f'مثبت قوی ({fr*100:.4f}%) - لانگ‌ها به شورت‌ها پرداخت (احتمال سقف)'
            analysis['funding_score'] = -2
        elif fr > 0.0001:
            analysis['funding_signal'] = f'مثبت ملایم ({fr*100:.4f}%)'
            analysis['funding_score'] = -1
        else:
            analysis['funding_signal'] = f'متعادل ({fr*100:.4f}%)'
            analysis['funding_score'] = 0

        # === Long/Short Ratio ===
        long_r = data.get('long_ratio', 0)
        short_r = data.get('short_ratio', 0)
        if long_r > 0 and short_r > 0:
            if short_r > 65:
                analysis['ls_signal'] = f'شورت‌ها غالب ({short_r:.0f}%) - احتمال short squeeze صعودی'
                analysis['ls_score'] = 2  # squeeze = صعودی
            elif long_r > 65:
                analysis['ls_signal'] = f'لانگ‌ها غالب ({long_r:.0f}%) - احتمال long squeeze نزولی'
                analysis['ls_score'] = -2  # squeeze = نزولی
            elif short_r > 55:
                analysis['ls_signal'] = f'شورت‌ها بیشتر ({short_r:.0f}%)'
                analysis['ls_score'] = 1
            elif long_r > 55:
                analysis['ls_signal'] = f'لانگ‌ها بیشتر ({long_r:.0f}%)'
                analysis['ls_score'] = -1
            else:
                analysis['ls_signal'] = f'متعادل (L:{long_r:.0f}% / S:{short_r:.0f}%)'
                analysis['ls_score'] = 0

        # === Open Interest + تغییر ===
        oi = data.get('oi_value', 0)
        oi_change = data.get('oi_change_pct', 0)
        if oi > 1_000_000_000:
            analysis['oi_signal'] = f'بسیار بالا (${oi/1e9:.1f}B)'
            analysis['oi_score'] = 2
        elif oi > 100_000_000:
            analysis['oi_signal'] = f'بالا (${oi/1e6:.0f}M)'
            analysis['oi_score'] = 1
        else:
            analysis['oi_signal'] = f'پایین (${oi/1e6:.0f}M)'
            analysis['oi_score'] = 0

        # OI تغییر + جهت قیمت = تشخیص ورود/خروج پول هوشمند
        if oi_change > 5:
            analysis['oi_flow_signal'] = 'ورود پول قوی (OI در حال افزایش)'
            analysis['oi_flow_score'] = 1
        elif oi_change < -5:
            analysis['oi_flow_signal'] = 'خروج پول قوی (OI در حال کاهش)'
            analysis['oi_flow_score'] = -1

        # === Liquidations ===
        long_liq = data.get('long_liquidations_24h', 0)
        short_liq = data.get('short_liquidations_24h', 0)
        total_liq = long_liq + short_liq
        if total_liq > 0:
            if long_liq > short_liq * 2:
                analysis['liq_signal'] = f'لیکوییداسیون لانگ‌ها غالب (${long_liq/1e6:.1f}M) - فشار فروش'
                analysis['liq_score'] = -1
            elif short_liq > long_liq * 2:
                analysis['liq_signal'] = f'لیکوییداسیون شورت‌ها غالب (${short_liq/1e6:.1f}M) - فشار خرید'
                analysis['liq_score'] = 1
            else:
                analysis['liq_signal'] = f'لیکوییداسیون متعادل (L:${long_liq/1e6:.1f}M / S:${short_liq/1e6:.1f}M)'
                analysis['liq_score'] = 0

        # === Buy/Sell Volume ===
        buy_pct = data.get('buy_pct', 50)
        if buy_pct > 60:
            analysis['volume_signal'] = f'فشار خرید ({buy_pct:.0f}% buy)'
            analysis['volume_score'] = 1
        elif buy_pct < 40:
            analysis['volume_signal'] = f'فشار فروش ({buy_pct:.0f}% buy)'
            analysis['volume_score'] = -1
        else:
            analysis['volume_signal'] = f'متعادل ({buy_pct:.0f}% buy)'
            analysis['volume_score'] = 0

        return analysis
