"""
ماژول تحلیل چند تایم‌فریم (Top-Down)
Multi-Timeframe Analysis Module
ترتیب تحلیل: 1d (24h) → 4h → 1h → 15m (نقطه ورود)
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import config
from indicators import Indicators
from liquidity import LiquidityAnalyzer


class MultiTimeframeAnalyzer:
    """
    تحلیل Top-Down:
    1) تایم فریم بالاتر (1d): تشخیص روند اصلی و جهت بازار
    2) تایم فریم میانی (4h): تأیید روند و یافتن فاز
    3) تایم فریم پایین (1h): ساختار قیمت و نقطه ورود تقریبی
    4) تایم فریم ورود (15m): نقطه ورود دقیق و تأیید نهایی
    """

    @staticmethod
    def analyze_all(timeframes_data: Dict[str, pd.DataFrame]) -> Dict:
        """
        تحلیل همه تایم فریم‌ها و تولید یک تحلیل یکپارچه
        """
        result = {}

        for tf in config.TIMEFRAMES:
            df = timeframes_data.get(tf)
            if df is None or len(df) < 50:
                result[tf] = None
                continue

            # محاسبه اندیکاتورها و تحلیل نقدینگی
            df_with_indicators = Indicators.compute_all(df)
            df_with_liquidity = LiquidityAnalyzer.compute_all(df_with_indicators)

            # استخراج وضعیت فعلی
            state = Indicators.get_current_state(df_with_indicators)
            liquidity = LiquidityAnalyzer.analyze(df_with_liquidity)
            sr = Indicators.find_support_resistance(df_with_indicators)

            result[tf] = {
                'state': state,
                'liquidity': liquidity,
                'sr': sr,
                'last_close': float(df_with_indicators['close'].iloc[-1]),
                'dataframe': df_with_indicators,
            }

        return result

    # ----------------- هماهنگی روند چند تایم فریم -----------------
    @staticmethod
    def check_trend_alignment(analysis: Dict) -> Dict:
        """
        بررسی هماهنگی روند در همه تایم فریم‌ها
        - اگر همه تایم‌فریم‌ها صعودی باشند → امتیاز لانگ بالا
        - اگر همه نزولی باشند → امتیاز شورت بالا
        - اگر متناقض باشند → سیگنال ضعیف
        """
        trend_scores = []
        trend_dirs = {}
        strengths = []

        for tf in config.TIMEFRAMES:
            tf_data = analysis.get(tf)
            if tf_data is None:
                trend_scores.append(0)
                trend_dirs[tf] = 'نامشخص'
                strengths.append('نامشخص')
                continue

            state = tf_data['state']
            trend_dirs[tf] = state.get('trend_dir', 'خنثی')
            strengths.append(state.get('trend_strength', 'ضعیف'))

            # امتیاز روند
            score = 0
            if state.get('trend_bullish'):
                score = 1
            elif state.get('trend_bearish'):
                score = -1

            # ضریب تایم فریم (تایم فریم بالاتر مهم‌تر)
            tf_weight = {'1d': 3, '4h': 2, '1h': 1.5, '15m': 1}.get(tf, 1)
            # ضریب قدرت روند
            strength_mult = {'قوی': 1.5, 'متوسط': 1.0, 'ضعیف': 0.5}.get(state.get('trend_strength', 'ضعیف'), 0.5)

            trend_scores.append(score * tf_weight * strength_mult)

        total_score = sum(trend_scores)
        max_possible = 3 * 1.5 + 2 * 1.5 + 1.5 * 1.5 + 1 * 1.5  # حداکثر امتیاز

        # نرمال‌سازی به درصد
        alignment_pct = (total_score / max_possible * 100) if max_possible > 0 else 0

        # جهت کلی
        if total_score > max_possible * 0.4:
            overall = 'صعودی قوی (Long Bias)'
        elif total_score > max_possible * 0.15:
            overall = 'صعودی ملایم'
        elif total_score < -max_possible * 0.4:
            overall = 'نزولی قوی (Short Bias)'
        elif total_score < -max_possible * 0.15:
            overall = 'نزولی ملایم'
        else:
            overall = 'خنثی/متناقض'

        return {
            'trend_dirs': trend_dirs,
            'strengths': strengths,
            'alignment_score': float(total_score),
            'alignment_pct': float(alignment_pct),
            'max_possible': float(max_possible),
            'overall_bias': overall,
        }

    # ----------------- تحلیل ساختار قیمت -----------------
    @staticmethod
    def analyze_structure(analysis: Dict) -> Dict:
        """
        تحلیل ساختار قیمت: انباشت، شکست، خروج
        در تایم فریم‌های 4h و 1h
        """
        structures = {}
        for tf in ['4h', '1h']:
            tf_data = analysis.get(tf)
            if tf_data is None:
                structures[tf] = {}
                continue
            liq = tf_data.get('liquidity', {})
            state = tf_data.get('state', {})

            structures[tf] = {
                'phase': liq.get('phase', 'خنثی'),
                'phase_score': liq.get('phase_score', 0),
                'volume_breakout': liq.get('volume_breakout', False),
                'volume_breakdown': liq.get('volume_breakdown', False),
                'cmf_state': liq.get('cmf_state', 'خنثی'),
                'mfi_state': liq.get('mfi_state', 'خنثی'),
                'obv_trend': liq.get('obv_trend', 'خنثی'),
                'accumulation_count': liq.get('accumulation_count', 0),
                'distribution_count': liq.get('distribution_count', 0),
            }

        # ساختار کلی
        phase_scores = [s.get('phase_score', 0) for s in structures.values()]
        total_phase_score = sum(phase_scores)

        if total_phase_score >= 3:
            overall_structure = 'انباشت قوی + آماده شکست صعودی'
        elif total_phase_score >= 1:
            overall_structure = 'انباشت ملایم'
        elif total_phase_score <= -3:
            overall_structure = 'توزیع قوی + آماده شکست نزولی'
        elif total_phase_score <= -1:
            overall_structure = 'توزیع ملایم'
        else:
            overall_structure = 'ساختار خنثی'

        return {
            'timeframes': structures,
            'total_phase_score': total_phase_score,
            'overall_structure': overall_structure,
        }

    # ----------------- تحلیل حجم برای ورود (1h و 15m) -----------------
    @staticmethod
    def analyze_volume_entry(analysis: Dict) -> Dict:
        """
        تحلیل حجم معاملات در تایم فریم‌های 1h و 15m برای تعیین نقطه ورود
        - حجم در حال افزایش = تایید ورود
        - حجم در حال کاهش = هشدار خروج/احتیاط
        - حجم ناگهانی (Spike) = سیگنال قوی ورود
        """
        result = {
            '1h': {},
            '15m': {},
            'entry_signal': 'خنثی',
            'entry_score': 0,
            'volume_trend': 'نامشخص',
            'recommendation': '',
        }

        for tf in ['1h', '15m']:
            tf_data = analysis.get(tf)
            if tf_data is None:
                continue

            df = tf_data.get('dataframe')
            state = tf_data.get('state', {})

            if df is None or len(df) < 20:
                continue

            # حجم 5 کندل اخیر
            recent_volume = df['volume'].tail(5)
            # میانگین حجم 20 کندل
            avg_volume = df['volume'].tail(20).mean()
            # حجم آخرین کندل
            last_volume = float(df['volume'].iloc[-1])
            # قیمت آخرین کندل
            last_close = float(df['close'].iloc[-1])
            # قیمت 5 کندل قبل
            prev_close = float(df['close'].iloc[-5])

            # نسبت حجم فعلی به میانگین
            vol_ratio = last_volume / avg_volume if avg_volume > 0 else 1

            # روند حجم (افزایشی/کاهشی)
            vol_ma5 = recent_volume.mean()
            vol_ma20 = avg_volume
            vol_trend = 'افزایشی' if vol_ma5 > vol_ma20 * 1.1 else 'کاهشی' if vol_ma5 < vol_ma20 * 0.9 else 'ثابت'

            # تغییر قیمت در 5 کندل اخیر
            price_change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close > 0 else 0

            # شناسایی Volume Spike (حجم ناگهانی)
            is_spike = vol_ratio > 2.0

            # شناسایی Volume Surge (افزایش حجم تدریجی)
            is_surge = vol_trend == 'افزایشی' and vol_ratio > 1.3

            # شناسایی Volume Dry Up (خشک شدن حجم)
            is_dry = vol_ratio < 0.5

            # تایید حجم با قیمت
            if vol_ratio > 1.3 and price_change_pct > 0:
                vol_price_confirm = 'تایید صعودی'  # حجم بالا + قیمت در حال رشد
            elif vol_ratio > 1.3 and price_change_pct < 0:
                vol_price_confirm = 'تایید نزولی'  # حجم بالا + قیمت در حال افت
            elif vol_ratio < 0.7:
                vol_price_confirm = 'عدم تایید (حجم کم)'
            else:
                vol_price_confirm = 'خنثی'

            result[tf] = {
                'last_volume': last_volume,
                'avg_volume': float(avg_volume),
                'vol_ratio': round(vol_ratio, 2),
                'vol_trend': vol_trend,
                'price_change_5candles_pct': round(price_change_pct, 2),
                'is_spike': is_spike,
                'is_surge': is_surge,
                'is_dry': is_dry,
                'vol_price_confirm': vol_price_confirm,
            }

        # محاسبه سیگنال ورود کلی
        entry_score = 0
        signals = []

        # تحلیل 1h
        h1 = result.get('1h', {})
        if h1:
            if h1.get('is_spike'):
                entry_score += 3
                signals.append(f"Spike حجم در 1h ({h1['vol_ratio']}x)")
            elif h1.get('is_surge'):
                entry_score += 2
                signals.append(f"Surge حجم در 1h ({h1['vol_ratio']}x)")
            elif h1.get('is_dry'):
                entry_score -= 2
                signals.append(f"حجم خشک در 1h ({h1['vol_ratio']}x)")

            if h1.get('vol_price_confirm') == 'تایید صعودی':
                entry_score += 1
            elif h1.get('vol_price_confirm') == 'تایید نزولی':
                entry_score -= 1

        # تحلیل 15m
        m15 = result.get('15m', {})
        if m15:
            if m15.get('is_spike'):
                entry_score += 2
                signals.append(f"Spike حجم در 15m ({m15['vol_ratio']}x)")
            elif m15.get('is_surge'):
                entry_score += 1
                signals.append(f"Surge حجم در 15m ({m15['vol_ratio']}x)")
            elif m15.get('is_dry'):
                entry_score -= 1
                signals.append(f"حجم خشک در 15m ({m15['vol_ratio']}x)")

            if m15.get('vol_price_confirm') == 'تایید صعودی':
                entry_score += 1
            elif m15.get('vol_price_confirm') == 'تایید نزولی':
                entry_score -= 1

        # تعیین سیگنال نهایی
        if entry_score >= 4:
            result['entry_signal'] = 'ورود قوی (حجم تایید می‌کند)'
            result['recommendation'] = 'حجم معاملات تایید کننده ورود است. نقطه ورود مناسب.'
        elif entry_score >= 2:
            result['entry_signal'] = 'ورود با احتیاط'
            result['recommendation'] = 'حجم متوسط است. با حجم کوچک‌تر وارد شوید.'
        elif entry_score <= -3:
            result['entry_signal'] = 'هشدار خروج'
            result['recommendation'] = 'حجم در حال کاهش است. از باز کردن پوزیشن جدید خودداری کنید.'
        elif entry_score <= -1:
            result['entry_signal'] = 'احتیاط (حجم کم)'
            result['recommendation'] = 'حجم پایین است. منتظر تایید حجم بمانید.'
        else:
            result['entry_signal'] = 'خنثی'
            result['recommendation'] = 'حجم نرمال است. منتظر سیگنال واضح‌تر بمانید.'

        result['entry_score'] = entry_score
        result['signals'] = signals
        result['volume_trend'] = h1.get('vol_trend', 'نامشخص') if h1 else 'نامشخص'

        return result
