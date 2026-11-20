"""
تشخیص ارزهای روند عکس (Inverse Trend) + پرایس اکشن
Inverse Trend Detector & Price Action Patterns

شناسایی ارزهایی که:
- در بازار نزولی، روند صعودی دارند
- نسبت به BTC قوی‌تر هستند
- ورود پول دارند
- الگوهای پرایس اکشن صعودی نشان می‌دهند

الگوهای پرایس اکشن:
- Bullish/Bearish Engulfing
- Pin Bar (Hammer/Shooting Star)
- Inside Bar breakout
- Double Bottom/Top
- Higher High / Lower Low
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class PriceActionAnalyzer:
    """تحلیل پرایس اکشن و الگوهای کندلی"""

    @staticmethod
    def analyze(df: pd.DataFrame) -> Dict:
        """
        تحلیل کامل پرایس اکشن
        """
        if df is None or len(df) < 20:
            return {'available': False}

        result = {'available': True, 'patterns': [], 'market_structure': ''}

        try:
            last = df.iloc[-1]
            prev = df.iloc[-2]
            prev2 = df.iloc[-3]

            open_p = float(last['open'])
            close_p = float(last['close'])
            high_p = float(last['high'])
            low_p = float(last['low'])

            prev_open = float(prev['open'])
            prev_close = float(prev['close'])
            prev_high = float(prev['high'])
            prev_low = float(prev['low'])

            body = abs(close_p - open_p)
            upper_wick = high_p - max(open_p, close_p)
            lower_wick = min(open_p, close_p) - low_p
            range_val = high_p - low_p

            # 1. Bullish Engulfing
            if prev_close < prev_open and close_p > open_p:
                if close_p >= prev_open and open_p <= prev_close:
                    result['patterns'].append({
                        'name': 'Bullish Engulfing',
                        'direction': 'bullish',
                        'strength': 'strong',
                        'description': 'کندل صعودی کامل کندل نزولی قبلی را پوشانده',
                    })

            # 2. Bearish Engulfing
            if prev_close > prev_open and close_p < open_p:
                if close_p <= prev_open and open_p >= prev_close:
                    result['patterns'].append({
                        'name': 'Bearish Engulfing',
                        'direction': 'bearish',
                        'strength': 'strong',
                        'description': 'کندل نزولی کامل کندل صعودی قبلی را پوشانده',
                    })

            # 3. Pin Bar / Hammer (صعودی)
            if lower_wick > body * 2 and upper_wick < body * 0.5:
                if close_p > open_p or (close_p < open_p and lower_wick > body * 3):
                    result['patterns'].append({
                        'name': 'Hammer / Pin Bar',
                        'direction': 'bullish',
                        'strength': 'medium',
                        'description': 'شاخ پایین بلند - ریجکت شدن قیمت از پایین',
                    })

            # 4. Shooting Star (نزولی)
            if upper_wick > body * 2 and lower_wick < body * 0.5:
                result['patterns'].append({
                    'name': 'Shooting Star',
                    'direction': 'bearish',
                    'strength': 'medium',
                    'description': 'شاخ بالا بلند - ریجکت شدن قیمت از بالا',
                })

            # 5. Inside Bar
            if high_p < prev_high and low_p > prev_low:
                result['patterns'].append({
                    'name': 'Inside Bar',
                    'direction': 'neutral',
                    'strength': 'low',
                    'description': 'کندل داخل کندل قبلی - انتظار شکست',
                })

            # 6. ساختار بازار (HH/HL or LH/LL)
            recent = df.tail(20)
            highs = recent['high'].values
            lows = recent['low'].values

            # Higher High / Higher Low = صعودی
            if len(highs) >= 4:
                if highs[-1] > highs[-3] and lows[-1] > lows[-3]:
                    result['market_structure'] = 'HH/HL - ساختار صعودی'
                    result['structure_dir'] = 'bullish'
                elif highs[-1] < highs[-3] and lows[-1] < lows[-3]:
                    result['market_structure'] = 'LH/LL - ساختار نزولی'
                    result['structure_dir'] = 'bearish'
                else:
                    result['market_structure'] = 'رنج - بدون ساختار مشخص'
                    result['structure_dir'] = 'neutral'

            # 7. Double Bottom / Double Top (5 کندل اخیر)
            if len(df) >= 10:
                recent_5 = df.tail(5)
                lows_5 = recent_5['low'].values
                highs_5 = recent_5['high'].values

                # Double Bottom
                if abs(lows_5[0] - lows_5[-1]) / lows_5[0] < 0.01 and lows_5[2] > lows_5[0]:
                    result['patterns'].append({
                        'name': 'Double Bottom',
                        'direction': 'bullish',
                        'strength': 'strong',
                        'description': 'دو کف هم‌سطح - الگوی برگشت صعودی',
                    })

                # Double Top
                if abs(highs_5[0] - highs_5[-1]) / highs_5[0] < 0.01 and highs_5[2] < highs_5[0]:
                    result['patterns'].append({
                        'name': 'Double Top',
                        'direction': 'bearish',
                        'strength': 'strong',
                        'description': 'دو سقف هم‌سطح - الگوی برگشت نزولی',
                    })

            # 8. حجم کندل اخیر
            vol_ratio = float(last.get('volume', 0)) / float(recent['volume'].mean()) if recent['volume'].mean() > 0 else 1
            result['volume_ratio'] = vol_ratio

            if vol_ratio > 2.0:
                result['patterns'].append({
                    'name': f'Volume Spike ({vol_ratio:.1f}x)',
                    'direction': 'bullish' if close_p > open_p else 'bearish',
                    'strength': 'strong',
                    'description': f'حجم {vol_ratio:.1f} برابر میانگین',
                })

            # جمع‌بندی جهت
            bull_count = sum(1 for p in result['patterns'] if p['direction'] == 'bullish')
            bear_count = sum(1 for p in result['patterns'] if p['direction'] == 'bearish')

            if bull_count > bear_count:
                result['overall'] = 'صعودی'
                result['score'] = bull_count * 10
            elif bear_count > bull_count:
                result['overall'] = 'نزولی'
                result['score'] = -bear_count * 10
            else:
                result['overall'] = 'خنثی'
                result['score'] = 0

        except Exception as e:
            logger.debug(f"خطا در پرایس اکشن: {e}")
            result['available'] = False

        return result


class InverseTrendDetector:
    """
    تشخیص ارزهایی که روند عکس بازار دارند

    منطق:
    - اگر BTC نزولی است ولی ارز/BTC صعودی است → ارز قوی‌تر از BTC
    - اگر ارز/USDT هم صعودی است → فرصت LONG واقعی
    - ورود پول (Volume Flow) تأیید کند
    """

    @staticmethod
    def detect(coin_data: Dict, btc_data: Dict, market_bearish: bool = True) -> Dict:
        """
        بررسی آیا ارز روند عکس دارد

        coin_data: داده ارز (USDT pair)
        btc_data: داده BTC pair ارز
        market_bearish: آیا بازار کلی نزولی است؟
        """
        result = {
            'is_inverse': False,
            'reason': '',
            'strength': 0,
            'recommendation': '',
        }

        if not btc_data or not btc_data.get('available'):
            return result

        btc_score = btc_data.get('btc_score', 0)
        btc_strength = btc_data.get('btc_strength', '')

        # اگر بازار نزولی است ولی ارز قوی‌تر از BTC است
        if market_bearish and btc_score > 0:
            result['is_inverse'] = True
            result['reason'] = f'ارز در بازار نزولی، قوی‌تر از BTC است ({btc_strength})'
            result['strength'] = btc_score

            change_4h = btc_data.get('4h', {}).get('change_24h_vs_btc_pct', 0)
            change_1h = btc_data.get('1h', {}).get('change_24h_vs_btc_pct', 0)

            if change_4h > 3 and change_1h > 1:
                result['strength'] += 2
                result['recommendation'] = '🟢 فرصت LONG قوی - ارز به‌طور قابل‌توجهی از BTC قوی‌تر'
            elif change_4h > 0:
                result['recommendation'] = '🟡 فرصت LONG متوسط - ارز کمی از BTC قوی‌تر'
            else:
                result['recommendation'] = '⚪ تحت نظر - قوی‌تر از BTC اما نه قاطع'

        # اگر بازار صعودی است ولی ارز ضعیف‌تر از BTC است
        elif not market_bearish and btc_score < 0:
            result['is_inverse'] = True
            result['reason'] = f'ارز در بازار صعودی، ضعیف‌تر از BTC است ({btc_strength})'
            result['strength'] = abs(btc_score)
            result['recommendation'] = '🔴 فرصت SHORT - ارز از BTC ضعیف‌تر'

        return result
