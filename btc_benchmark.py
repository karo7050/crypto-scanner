"""
ماژول تحلیل نسبت به BTC (BTC Pair Analysis)
BTC Benchmark Analyzer

بررسی قدرت ارز نسبت به بیت‌کوین:
- اگر ارز/USDT صعودی و ارز/BTC هم صعودی → لانگ قوی (ارز از BTC قوی‌تر)
- اگر ارز/USDT صعودی اما ارز/BTC نزولی → لانگ ضعیف (فقط دنبال BTC حرکت می‌کند)
- اگر ارز/USDT نزولی و ارز/BTC هم نزولی → شورت قوی (ارز از BTC ضعیف‌تر)
- اگر ارز/USDT نزولی اما ارز/BTC صعودی → شورت ضعیف (BTC کشیده پایین)

این تحلیل در تایم فریم‌های 4h و 1h انجام می‌شود.
"""
import pandas as pd
import numpy as np
from typing import Dict
import ta
import logging

logger = logging.getLogger(__name__)


class BTCBenchmarkAnalyzer:
    """تحلیل قدرت ارز نسبت به بیت‌کوین"""

    @staticmethod
    def analyze_btc_pair(btc_pair_data: Dict) -> Dict:
        """
        تحلیل جفت ارز/BTC در تایم فریم‌های مختلف
        """
        if not btc_pair_data:
            return {'available': False}

        result = {
            'available': True,
            '4h': {},
            '1h': {},
            'btc_strength': 'unknown',  # ارز قوی‌تر یا ضعیف‌تر از BTC
            'btc_score': 0,  # امتیاز قدرت نسبت به BTC
        }

        for tf in ['4h', '1h']:
            df = btc_pair_data.get(tf)
            if df is None or len(df) < 50:
                continue

            df = df.copy()

            # محاسبه EMA
            df['ema_fast'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
            df['ema_slow'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
            df['ema_trend'] = ta.trend.EMAIndicator(df['close'], window=200).ema_indicator() if len(df) >= 200 else df['ema_slow']

            # RSI
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

            # MACD
            macd = ta.trend.MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
            df['macd'] = macd.macd()
            df['macd_diff'] = macd.macd_diff()

            # حجم
            df['volume_ma'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']

            last = df.iloc[-1]

            # تعیین روند BTC pair
            price = float(last['close'])
            ema_fast = float(last['ema_fast']) if not np.isnan(last['ema_fast']) else price
            ema_slow = float(last['ema_slow']) if not np.isnan(last['ema_slow']) else price
            rsi = float(last['rsi']) if not np.isnan(last['rsi']) else 50
            macd_diff = float(last['macd_diff']) if not np.isnan(last['macd_diff']) else 0
            vol_ratio = float(last['volume_ratio']) if not np.isnan(last['volume_ratio']) else 1

            # روند
            if ema_fast > ema_slow and price > ema_slow:
                trend = 'صعودی نسبت به BTC'  # ارز در حال تقویت نسبت به BTC
                trend_dir = 'bullish_vs_btc'
                trend_score = 1
            elif ema_fast < ema_slow and price < ema_slow:
                trend = 'نزولی نسبت به BTC'  # ارز در حال تضعیف نسبت به BTC
                trend_dir = 'bearish_vs_btc'
                trend_score = -1
            else:
                trend = 'خنثی نسبت به BTC'
                trend_dir = 'neutral_vs_btc'
                trend_score = 0

            # تغییر قیمت 24h نسبت به BTC
            if len(df) >= 24:
                price_24h_ago = float(df['close'].iloc[-24])
                change_24h_vs_btc = ((price - price_24h_ago) / price_24h_ago) * 100
            else:
                change_24h_vs_btc = 0

            # تغییر قیمت 7 روز نسبت به BTC
            if len(df) >= 42:  # 7 روز * 6 کندل 4h
                price_7d_ago = float(df['close'].iloc[-42])
                change_7d_vs_btc = ((price - price_7d_ago) / price_7d_ago) * 100
            else:
                change_7d_vs_btc = 0

            result[tf] = {
                'trend': trend,
                'trend_dir': trend_dir,
                'trend_score': trend_score,
                'rsi': rsi,
                'macd_diff': macd_diff,
                'volume_ratio': vol_ratio,
                'change_24h_vs_btc_pct': round(change_24h_vs_btc, 2),
                'change_7d_vs_btc_pct': round(change_7d_vs_btc, 2),
                'price_vs_btc': price,
            }

        # محاسبه امتیاز کلی قدرت نسبت به BTC
        # 4h وزن بیشتر (2x) نسبت به 1h (1x)
        score_4h = result.get('4h', {}).get('trend_score', 0) * 2
        score_1h = result.get('1h', {}).get('trend_score', 0) * 1

        # تغییرات قیمت نسبت به BTC
        change_4h = result.get('4h', {}).get('change_24h_vs_btc_pct', 0)
        change_1h = result.get('1h', {}).get('change_24h_vs_btc_pct', 0)

        # امتیاز تغییر قیمت: بالای 0 = قوی‌تر از BTC
        price_score = 0
        if change_4h > 2:
            price_score += 1
        elif change_4h < -2:
            price_score -= 1

        total_score = score_4h + score_1h + price_score

        if total_score >= 2:
            result['btc_strength'] = 'قوی‌تر از BTC (outperforming)'
            result['btc_score'] = 2  # تایید لانگ
        elif total_score >= 1:
            result['btc_strength'] = 'کمی قوی‌تر از BTC'
            result['btc_score'] = 1
        elif total_score <= -2:
            result['btc_strength'] = 'ضعیف‌تر از BTC (underperforming)'
            result['btc_score'] = -2  # تایید شورت
        elif total_score <= -1:
            result['btc_strength'] = 'کمی ضعیف‌تر از BTC'
            result['btc_score'] = -1
        else:
            result['btc_strength'] = 'هم‌تراز با BTC'
            result['btc_score'] = 0

        return result

    @staticmethod
    def get_confirmation(usdt_trend_dir: str, btc_score: int, is_long: bool) -> Dict:
        """
        تأیید سیگنال بر اساس BTC pair
        """
        if btc_score == 0:
            return {
                'confirmation': 'خنثی',
                'strength_multiplier': 1.0,
                'note': 'ارز هم‌تراز با BTC - تایید خاصی ندارد'
            }

        if is_long:
            if btc_score > 0:
                # ارز قوی‌تر از BTC + لانگ → تایید قوی
                return {
                    'confirmation': '✅ تایید قوی (قوی‌تر از BTC)',
                    'strength_multiplier': 1.2,
                    'note': 'ارز از BTC قوی‌تر است - لانگ با اعتماد بیشتر'
                }
            else:
                # ارز ضعیف‌تر از BTC + لانگ → هشدار
                return {
                    'confirmation': '⚠ هشدار (ضعیف‌تر از BTC)',
                    'strength_multiplier': 0.7,
                    'note': 'ارز از BTC ضعیف‌تر است - ممکن است فقط دنبال BTC حرکت کند'
                }
        else:  # SHORT
            if btc_score < 0:
                # ارز ضعیف‌تر از BTC + شورت → تایید قوی
                return {
                    'confirmation': '✅ تایید قوی (ضعیف‌تر از BTC)',
                    'strength_multiplier': 1.2,
                    'note': 'ارز از BTC ضعیف‌تر است - شورت با اعتماد بیشتر'
                }
            else:
                # ارز قوی‌تر از BTC + شورت → هشدار
                return {
                    'confirmation': '⚠ هشدار (قوی‌تر از BTC)',
                    'strength_multiplier': 0.7,
                    'note': 'ارز از BTC قوی‌تر است - شورت خطرناک، ممکن است بایک کند'
                }
